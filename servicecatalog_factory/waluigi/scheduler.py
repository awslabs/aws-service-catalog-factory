import queue
import threading
import time
import traceback

import networkx as nx

from servicecatalog_factory import constants, environmental_variables
from servicecatalog_factory.common import serialisation_utils, utils

import os

from servicecatalog_factory.workflow.dependencies import task_factory


import logging


logger = logging.getLogger(constants.FACTORY_SCHEDULER_LOGGER_NAME)

COMPLETED = "COMPLETED"
NOT_SET = "NOT_SET"
ERRORED = "ERRORED"
QUEUE_STATUS = "QUEUE_STATUS"

RESOURCES_REQUIRED = "resources_required"


def build_the_dag(tasks_to_run):
    g = nx.DiGraph()
    print("-- BUILDING THE DAG!!!")
    for uid, task in tasks_to_run.items():
        g.add_nodes_from(
            [(uid, task),]
        )
        for duid in task.get("dependencies_by_reference", []):
            if tasks_to_run.get(duid):
                g.add_edge(uid, duid)
            else:
                logger.warn(
                    f"{duid} is not in the task reference - this is fine when running in spoke execution mode and when the task was executed within the hub"
                )

    for uid, task in tasks_to_run.items():
        if task.get(QUEUE_STATUS, NOT_SET) == COMPLETED:
            try:
                g.remove_node(uid)
            except nx.exception.NetworkXError as e:
                pass

        elif task.get(QUEUE_STATUS, NOT_SET) == ERRORED:
            print(
                f"looking at task {uid} with status {task.get(QUEUE_STATUS, NOT_SET)}"
            )
            for n in nx.ancestors(g, uid):
                try:
                    g.remove_node(n)
                except nx.exception.NetworkXError as e:
                    pass
            try:
                g.remove_node(uid)
            except nx.exception.NetworkXError as e:
                pass

    return g


def are_resources_are_free_for_task(task_parameters, resources_file_path):
    with open(resources_file_path, "rb") as f:
        resources_in_use = serialisation_utils.json_loads(f.read())
    return (
        all(
            resources_in_use.get(r, False) is False
            for r in task_parameters.get(RESOURCES_REQUIRED, [])
        ),
        resources_in_use,
    )


def lock_resources_for_task(
    task_reference, task_parameters, resources_in_use, resources_file_path
):
    print(f"Worker locking {task_reference}")
    for r in task_parameters.get(RESOURCES_REQUIRED, []):
        resources_in_use[r] = task_reference
    with open(resources_file_path, "wb") as f:
        f.write(serialisation_utils.json_dumps(resources_in_use))


def unlock_resources_for_task(task_parameters, resources_file_path):
    with open(resources_file_path, "rb") as f:
        resources_in_use = serialisation_utils.json_loads(f.read())
    for r in task_parameters.get(RESOURCES_REQUIRED, []):
        try:
            del resources_in_use[r]
        except KeyError:
            logger.warn(
                f"{task_parameters.get('task_reference')} tried to unlock {r} but it wasn't present"
            )
    with open(resources_file_path, "wb") as f:
        f.write(serialisation_utils.json_dumps(resources_in_use))


def worker_task(
    thread_name,
    lock,
    task_queue,
    results_queue,
    task_processing_time_queue,
    task_trace_queue,
    control_event,
    tasks_to_run,
    manifest_files_path,
    manifest_task_reference_file_path,
    puppet_account_id,
    resources_file_path,
):
    logger.info(f"starting up")
    while not control_event.is_set():
        time.sleep(0.1)
        try:
            task_reference = task_queue.get(timeout=5)
        except queue.Empty:
            continue
        else:
            result = False
            while not result:
                # print(
                #     f"{pid} Worker received {task_reference} waiting for lock",
                #     flush=True,
                # )
                task_parameters = tasks_to_run.get(task_reference)
                # print(
                #     f"{pid} Worker received {task_reference} waiting for lock and the task is {task_parameters}",
                #     flush=True,
                # )

                with lock:
                    # print(f"{pid} Worker {task_reference} got the lock", flush=True)
                    (
                        resources_are_free,
                        resources_in_use,
                    ) = are_resources_are_free_for_task(
                        task_parameters, resources_file_path
                    )
                    # print(
                    #     f"{pid} Worker {task_reference} resources_are_free: {resources_are_free}",
                    #     flush=True,
                    # )
                    if resources_are_free:
                        lock_resources_for_task(
                            task_reference,
                            task_parameters,
                            resources_in_use,
                            resources_file_path,
                        )
                        # print(f"{pid} Worker {task_reference} locked", flush=True)

                if resources_are_free:
                    # print(f"{pid} Worker about to run {task_reference}", flush=True)
                    task = task_factory.create(
                        manifest_files_path=manifest_files_path,
                        manifest_task_reference_file_path=manifest_task_reference_file_path,
                        parameters_to_use=task_parameters,
                    )
                    logger.info(f"executing task: {task_reference}")
                    task.on_task_start()
                    start = time.time()
                    task_type, task_details = task.get_processing_time_details()
                    task_trace_queue.put(
                        (start, task_type, task_details, True, thread_name),
                    )
                    try:
                        task.execute()
                    except Exception as e:
                        end = time.time()
                        duration = end - start
                        result = ERRORED
                        logger.error(
                            f"executed task [failure]: {task_reference} failures: {e}"
                        )
                        logger.error(f"---- START OF ERROR----")
                        logger.error(f"Task {task_type}:")
                        for l in serialisation_utils.dump(
                            utils.unwrap(task_details)
                        ).split("\n"):
                            logger.error(l)
                        for l in traceback.format_exception(
                            etype=type(e), value=e, tb=e.__traceback__,
                        ):
                            for sl in l.split("\n"):
                                logger.error(f"{sl}")
                        logger.error(f"---- END OF ERROR ----")
                        task.on_task_failure(e, duration)
                    else:
                        end = time.time()
                        duration = end - start
                        result = COMPLETED
                        task.on_task_success(duration)

                    task_processing_time_queue.put(
                        (duration, task_type, task_details,),
                    )
                    task_trace_queue.put(
                        (end, task_type, task_details, False, thread_name),
                    )

                    # print(f"{pid} Worker {task_reference} waiting for lock to unlock resources", flush=True)
                    with lock:
                        logger.info(
                            f"executed task [success]: {task_reference} got lock to unlock resources"
                        )
                        unlock_resources_for_task(task_parameters, resources_file_path)
                        results_queue.put((task_reference, result))
                        time.sleep(0.1)
                else:
                    time.sleep(0.01)

        # time.sleep(10)
    logger.info(f"shutting down")


def scheduler_task(
    num_workers, task_queue, results_queue, control_event, complete_event, tasks_to_run,
):
    number_of_target_tasks_in_flight = num_workers
    while not control_event.is_set():
        dag = build_the_dag(tasks_to_run)
        generations = list(nx.topological_generations(dag))
        if not generations:
            logger.info("No more batches to run")
            control_event.set()
            return

        current_generation = list(generations[-1])  # may need to make list
        number_of_tasks_in_flight = 0
        number_of_tasks_processed = 0
        number_of_tasks_in_generation = len(current_generation)
        current_generation_in_progress = True

        while current_generation_in_progress:
            logger.info("starting batch")
            # start each iteration by checking if the queue has enough jobs in it
            while (
                current_generation
                and number_of_tasks_in_flight < number_of_target_tasks_in_flight
            ):
                # there are enough jobs in the queue
                number_of_tasks_in_flight += 1
                task_to_run_reference = current_generation.pop()
                logger.info(f"sending: {task_to_run_reference}")
                task_queue.put(task_to_run_reference)

            # now handle a complete jobs from the workers
            task_reference, result = results_queue.get()
            if task_reference:
                number_of_tasks_in_flight -= 1
                number_of_tasks_processed += 1
                logger.info(
                    f"receiving: [{number_of_tasks_processed}]: {task_reference}, {result}"
                )
                tasks_to_run[task_reference][QUEUE_STATUS] = result

            if not current_generation:  # queue now empty - wait for all to complete
                logger.info("tasks now scheduled")
                while number_of_tasks_processed < number_of_tasks_in_generation:
                    task_reference, result = results_queue.get()
                    if task_reference:
                        number_of_tasks_in_flight -= 1
                        number_of_tasks_processed += 1
                        logger.info(
                            f"receiving: [{number_of_tasks_processed}]: {task_reference}, {result}"
                        )
                        tasks_to_run[task_reference][QUEUE_STATUS] = result
                else:
                    current_generation_in_progress = False
                    logger.info("finished batch")
    logger.info("finished all batches")


def on_task_processing_time(task_processing_time_queue, complete_event):
    pass
    # TODO implement
    # with betterboto_client.CrossAccountClientContextManager(
    #     "cloudwatch",
    #     config.get_puppet_role_arn(config.get_executor_account_id()),
    #     "cloudwatch-puppethub",
    # ) as cloudwatch:
    #     while not complete_event.is_set():
    #         time.sleep(0.1)
    #         try:
    #             duration, task_type, task_params = task_processing_time_queue.get(
    #                 timeout=5
    #             )
    #         except queue.Empty:
    #             continue
    #         else:
    #             dimensions = [
    #                 dict(Name="task_type", Value=task_type,),
    #                 dict(
    #                     Name="codebuild_build_id",
    #                     Value=os.getenv("CODEBUILD_BUILD_ID", "LOCAL_BUILD"),
    #                 ),
    #             ]
    #             for note_worthy in [
    #                 "launch_name",
    #                 "region",
    #                 "account_id",
    #                 "puppet_account_id",
    #                 "portfolio",
    #                 "product",
    #                 "version",
    #             ]:
    #                 if task_params.get(note_worthy):
    #                     dimensions.append(
    #                         dict(
    #                             Name=str(note_worthy),
    #                             Value=str(task_params.get(note_worthy)),
    #                         )
    #                     )
    #             cloudwatch.put_metric_data(
    #                 Namespace=f"ServiceCatalogTools/Puppet/v2/ProcessingTime/Tasks",
    #                 MetricData=[
    #                     dict(
    #                         MetricName="Tasks",
    #                         Dimensions=[dict(Name="TaskType", Value=task_type)]
    #                         + dimensions,
    #                         Value=duration,
    #                         Unit="Seconds",
    #                     ),
    #                 ],
    #             )
    #     logger.info("shutting down")


def on_task_trace(task_trace_queue, complete_event, puppet_account_id):
    # TODO implement
    pass
    # bucket = f"sc-puppet-log-store-{puppet_account_id}"
    # key_prefix = f"{os.getenv('CODEBUILD_BUILD_ID', f'local/{os.getenv(environmental_variables.CACHE_INVALIDATOR)}')}/traces"
    # with betterboto_client.CrossAccountClientContextManager(
    #     "s3", config.get_puppet_role_arn(config.get_executor_account_id()), "s3",
    # ) as s3:
    #     while not complete_event.is_set():
    #         time.sleep(0.1)
    #         try:
    #             t, task_type, task_params, is_start, thread_name = task_trace_queue.get(
    #                 timeout=5
    #             )
    #         except queue.Empty:
    #             continue
    #         else:
    #             tz = (t - float(os.getenv("SCT_START_TIME", 0))) * 1000000
    #             task_reference = task_params.get("task_reference")
    #             s3.put_object(
    #                 Bucket=bucket,
    #                 Key=f"{key_prefix}/{tz}-{utils.escape(task_reference)}-{'start' if is_start else 'end'}.json",
    #                 Body=serialisation_utils.json_dumps(
    #                     {
    #                         "name": task_reference,
    #                         "cat": task_type,
    #                         "ph": "B" if is_start else "E",
    #                         "pid": 1,
    #                         "tid": thread_name,
    #                         "ts": tz,
    #                         "args": utils.unwrap(task_params),
    #                     }
    #                 ),
    #             )
    #
    #     logger.info("shutting down")


def run(
    num_workers,
    tasks_to_run,
    manifest_files_path,
    manifest_task_reference_file_path,
    puppet_account_id,
):
    resources_file_path = f"{manifest_files_path}/resources.json"
    os.environ["SCT_START_TIME"] = str(time.time())

    logger.info(f"Running with {num_workers} processes!")
    start = time.time()
    lock = threading.Lock()

    with open(resources_file_path, "w") as f:
        f.write("{}")

    task_queue = queue.Queue()
    results_queue = queue.Queue()
    task_processing_time_queue = queue.Queue()
    task_trace_queue = queue.Queue()
    control_event = threading.Event()
    complete_event = threading.Event()

    processes = [
        threading.Thread(
            name=f"worker#{i}",
            target=worker_task,
            args=(
                str(i),
                lock,
                task_queue,
                results_queue,
                task_processing_time_queue,
                task_trace_queue,
                control_event,
                tasks_to_run,
                manifest_files_path,
                manifest_task_reference_file_path,
                puppet_account_id,
                resources_file_path,
            ),
        )
        for i in range(num_workers)
    ]
    scheduler_thread = threading.Thread(
        name="scheduler",
        target=scheduler_task,
        args=(
            num_workers,
            task_queue,
            results_queue,
            control_event,
            complete_event,
            tasks_to_run,
        ),
    )
    on_task_processing_time_thread = threading.Thread(
        name="on_task_processing_time",
        target=on_task_processing_time,
        args=(task_processing_time_queue, complete_event,),
    )
    on_task_trace_thread = threading.Thread(
        name="on_task_trace",
        target=on_task_trace,
        args=(task_trace_queue, complete_event, puppet_account_id),
    )
    on_task_processing_time_thread.start()
    on_task_trace_thread.start()
    for process in processes:
        process.start()
    scheduler_thread.start()
    while not control_event.is_set():
        time.sleep(5)
    for process in processes:
        process.join(timeout=1)
    time.sleep(10)
    complete_event.set()
    logger.info(f"Time taken = {time.time() - start:.10f}")
