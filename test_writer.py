import parso
import glob

from parso.python import tree

ignored = [
    "get_sharing_policies",
    "output_suffix",
    "get_all_params",
    "complete",
    "load_from_input",
    "generate_new_launch_constraints",
    "read_from_input",
    "info",
    "get_portfolio",
    "manifest",
    "retry_count",
    "priority",
    "output",
    "output_location",
    "get_current_version",
    "write_result",
    "generate_tasks",
    "generate_provisions",
    "get_launch_tasks_defs",
    "get_task_defs",
    "delete_pipelines",
    "delete_from_service_catalog",
    "handle_terraform_provisioner",
    "handle_cloudformation_provisioner",
    "resources",
]

HEADER = """from unittest import skip
from . import tasks_unit_tests_helper


"""

global_params = dict(
    account_parameters=dict(),
    associations=list(),
    depends_on=list(),
    iam_role_arns=list(),
    include_expanded_from=False,
    is_dry_run=False,
    launch_constraints=dict(),
    launch_parameters=dict(),
    manifest_parameters=dict(),
    parameters=dict(),
    regions=list(),
    requested_priority=1,
    retry_count=1,
    sharing_policies=dict(),
    should_collect_cloudformation_events=False,
    should_forward_events_to_eventbridge=False,
    should_forward_failures_to_opscenter=False,
    should_use_product_plans=False,
    should_use_sns=False,
    ssm_param_inputs=list(),
    ssm_param_outputs=list(),
    worker_timeout=3,

    account_id="account_id",
    cache_invalidator="cache_invalidator",
    execution="execution",
    execution_mode="execution_mode",
    function_name="function_name",
    home_region="home_region",
    invocation_type="invocation_type",
    lambda_invocation_name="lambda_invocation_name",
    launch_name="launch_name",
    manifest_file_path="manifest_file_path",
    name="name",
    organization="organization",
    ou_to_share_with="ou_to_share_with",
    parameter_name="parameter_name",
    permission_boundary="permission_boundary",
    phase="phase",
    portfolio="portfolio",
    portfolio_id="portfolio_id",
    product_generation_method="product_generation_method",
    product_id="product_id",
    project_name="project_name",
    puppet_account_id="puppet_account_id",
    puppet_role_name="puppet_role_name",
    puppet_role_path="puppet_role_path",
    qualifier="qualifier",
    region="region",
    role_name="role_name",
    section="section",
    sharing_mode="sharing_mode",
    single_account="single_account",
    source="source",
    source_type="source_type",
    spoke_local_portfolio_name="spoke_local_portfolio_name",
    stack_name="stack_name",
    type="type",
    version_id="version_id",
    all_params=[],
    try_count=1,

    portfolio_group_name="ccoe",
    display_name="self-service",
    description="portfolio for sharing",
    provider_name="ccoe",
    tags=[],
    factory_version='',
    uid="",
    owner="",
    distributor="ccoe",
    support_description="contact us",
    support_email="someone@somewhere.com",
    support_url="https://wiki",
    pipeline_mode="combined", #TODO
    portfolio_args=None, #TODO
    product_args=None, #TODO
    all_regions=None, #TODO
    provisioner=None, #TODO
    template=None, #TODO
    products_args_by_region=None, #TODO

    product = dict(),
    version = dict(),
)


def handle_params_for_results_display(f, output):
    returns = list(f.iter_return_stmts())
    if len(returns) != 1:
        raise Exception("unexpected")

    expected = returns[0].get_code()
    open(output, 'a+').write(f"""
    def test_params_for_results_display(self):
        # setup
{expected.replace("return", "expected_result =")}        
    
        # exercise
        actual_result = self.sut.params_for_results_display()
        
        # verify
        self.assertEqual(expected_result, actual_result)
    """)


def handle_api_calls_used(f, output):
    returns = list(f.iter_return_stmts())
    if len(returns) != 1:
        raise Exception("unexpected")

    expected = returns[0].get_code()
    open(output, 'a+').write(f"""
    def test_api_calls_used(self):
        # setup
{expected.replace("return", "expected_result =")}        
    
        # exercise
        actual_result = self.sut.api_calls_used()
        
        # verify
        self.assertEqual(expected_result, actual_result)
    """)


def handle_requires(f, output, mod, classes):
    open(output, 'a+').write(f"""
    @skip
    def test_requires(self):
        # setup
        # exercise
        actual_result = self.sut.requires()

        # verify
        raise NotImplementedError()
    """)


def handle_run(f, output, mod, classes):
    open(output, 'a+').write(f"""
    @skip
    def test_run(self):
        # setup
        # exercise
        actual_result = self.sut.run()

        # verify
        raise NotImplementedError()
    """)


def handle(c, output, mod, classes):
    for f in c.iter_funcdefs():
        name = f.name.value
        if name == "params_for_results_display":
            handle_params_for_results_display(f, output)
        elif name == "requires":
            handle_requires(f, output, mod, classes)
        elif name == "api_calls_used":
            handle_api_calls_used(f, output)
        elif name == "run":
            handle_run(f, output, mod, classes)
        elif name in ignored:
            pass
        else:
            raise Exception(f"unhandled: {name}")

def handle_function(f, output, mod, classes):
    name = f.name.value
    if name == "params_for_results_display":
        handle_params_for_results_display(f, output)
    elif name == "requires":
        handle_requires(f, output, mod, classes)
    elif name == "api_calls_used":
        handle_api_calls_used(f, output)
    elif name == "run":
        handle_run(f, output, mod, classes)
    elif name in ignored:
        pass
    else:
        raise Exception(f"unhandled: {name}")

def get_initial_args_for(c):
    supers = c.get_super_arglist().get_code()
    if "SectionTask" in supers:
        return dict(
            manifest_file_path=global_params.get('manifest_file_path'),
            puppet_account_id=global_params.get("puppet_account_id"),
            should_use_sns=global_params.get("should_use_sns"),
            should_use_product_plans=global_params.get("should_use_product_plans"),
            include_expanded_from=global_params.get("include_expanded_from"),
            single_account=global_params.get("single_account"),
            is_dry_run=global_params.get("is_dry_run"),
            execution_mode=global_params.get("execution_mode"),
            cache_invalidator=global_params.get("cache_invalidator"),
        )
    elif "PortfolioManagementTask" in supers:
        return dict(
            manifest_file_path=global_params.get('manifest_file_path'),
        )
    elif "ProvisioningTask" in supers:
        return dict(
            manifest_file_path=global_params.get('manifest_file_path'),
        )
    elif "ProvisionProductTask" in supers:
        return dict(
            manifest_file_path=global_params.get('manifest_file_path'),

            launch_name=global_params.get("launch_name"),
            portfolio=global_params.get("portfolio"),
            portfolio_id=global_params.get("portfolio_id"),
            product=global_params.get("product"),
            product_id=global_params.get("product_id"),
            version=global_params.get("version"),
            version_id=global_params.get("version_id"),
            region=global_params.get("region"),
            account_id=global_params.get("account_id"),

            puppet_account_id=global_params.get("puppet_account_id"),

            parameters=global_params.get("parameters"),
            ssm_param_inputs=global_params.get("ssm_param_inputs"),

            launch_parameters=global_params.get("launch_parameters"),
            manifest_parameters=global_params.get("manifest_parameters"),
            account_parameters=global_params.get("account_parameters"),

            retry_count=global_params.get("retry_count"),
            worker_timeout=global_params.get("worker_timeout"),
            ssm_param_outputs=global_params.get("ssm_param_outputs"),
            should_use_sns=global_params.get("should_use_sns"),
            should_use_product_plans=global_params.get("should_use_product_plans"),
            requested_priority=global_params.get("requested_priority"),

            execution=global_params.get("execution"),

            cache_invalidator=global_params.get("cache_invalidator"),

        )
    return dict()


for input in glob.glob("servicecatalog_factory/luigi_tasks_and_targets.py", recursive=True):
    if input.endswith("_tests.py") or input.endswith("_test.py") or input.endswith("tasks_unit_tests_helper.py") or input.endswith("__init__.py"):
        continue
    mod = input.split('/')[-1].replace('.py', '')
    print(f"Starting {input}")
    output = input.replace(".py", "_test.py")
    open(output, 'w+').write(HEADER)
    code = open(input, 'r').read()
    module = parso.parse(code, version="3.7")
    index = 0
    classes = list()

    for c in module.iter_classdefs():
        classes.append(c.name.value)
    for c in module.iter_classdefs():
        if c.name.value in ["FactoryTask", "PuppetTask", "ManifestMixen"]:
            continue

        # if c.name.value not in ["DeleteCloudFormationStackTask"]:
        #     continue

        open(output, "a+").write(f"""
class {c.name.value}Test(tasks_unit_tests_helper.FactoryTaskUnitTest):
""")
        suite = c.children[-1]
        params = get_initial_args_for(c)
        for p in params.keys():
            if isinstance(params.get(p), str):
                open(output, "a+").write(f"    {p} = \"{params.get(p)}\"\n")
            else:
                open(output, "a+").write(f"    {p} = {params.get(p)}\n")
        for child in suite.children:
            # if isinstance(child, tree.Function):
                # handle_function(child, output, mod, classes)
                # print(child.name.value)
            if isinstance(child, tree.PythonNode):
                if child.type == "simple_stmt":
                    parameter = child.children[0]
                    if isinstance(parameter, tree.ExprStmt):  # ignore docstrings for classes
                        parameter_name = parameter.children[0].value
                        parameter_value = parameter.children[2]

                        if isinstance(parameter_value, tree.Number):  # literal numbers
                            pass
                            # parameter_value = global_params[parameter_name]
                            # params[parameter_name] = parameter_value
                            # open(output, "a+").write(f"    {parameter_name} = {parameter_value}#1\n")

                        elif isinstance(parameter_value, tree.PythonNode):  # everything else
                            if parameter_value.type == "atom_expr":
                                parameter_type = parameter_value.children[1].children[1].value
                                parameter_value = global_params[parameter_name]
                                params[parameter_name] = parameter_value
                                if parameter_type == "Parameter":
                                    open(output, "a+").write(f"    {parameter_name} = \"{parameter_value}\"\n")
                                else:
                                    open(output, "a+").write(f"    {parameter_name} = {parameter_value}\n")
                            elif parameter_value.type == "atom":
                                pass
                                # parameter_value = global_params[parameter_name]
                                # params[parameter_name] = parameter_value
                                # open(output, "a+").write(f"    {parameter_name} = {parameter_value}#3\n")
                            else:
                                raise Exception(f"unhandled {parameter_name}: {parameter_value}")
                        else:
                            raise Exception(f"cannot handle {type(parameter_value)}")


        open(output, "a+").write(f"""
    def setUp(self) -> None:
        from servicecatalog_factory import {mod}
        self.module = {mod}
        
        self.sut = self.module.{c.name.value}(
            {", ".join([f"{p}=self.{p}" for p in params.keys()])}        
        )
        
        self.wire_up_mocks()    
""")
        handle(c, output, mod, classes)
    # raise Exception("endin")
