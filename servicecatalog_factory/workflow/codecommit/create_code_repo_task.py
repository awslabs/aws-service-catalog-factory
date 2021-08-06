#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import io
import zipfile

import luigi

from servicecatalog_factory.workflow.tasks import FactoryTask


class CreateCodeRepoTask(FactoryTask):
    repository_name = luigi.Parameter()
    branch_name = luigi.Parameter()
    bucket = luigi.Parameter()
    key = luigi.Parameter()

    def params_for_results_display(self):
        return {
            "repository_name": self.repository_name,
            "branch_name": self.branch_name,
        }

    def run(self):
        with self.client("s3") as s3:
            z = zipfile.ZipFile(
                io.BytesIO(
                    s3.get_object(Bucket=self.bucket, Key=self.key).get("Body").read()
                )
            )
            files = list()
            for f in z.namelist():
                files.append(
                    dict(
                        filePath=f,
                        fileMode="NORMAL",
                        fileContent=z.open(f, "r").read(),
                    )
                )
        with self.client("codecommit") as codecommit:
            try:
                repo = codecommit.get_repository(
                    repositoryName=self.repository_name
                ).get("repositoryMetadata")
            except codecommit.exceptions.RepositoryDoesNotExistException:
                repo = codecommit.create_repository(
                    repositoryName=self.repository_name
                ).get("repositoryMetadata")

            if repo.get("defaultBranch"):
                try:
                    codecommit.get_branch(
                        repositoryName=self.repository_name,
                        branchName=self.branch_name,
                    ).get("branch")
                except codecommit.exceptions.BranchDoesNotExistException:
                    default_branch = codecommit.get_branch(
                        repositoryName=self.repository_name,
                        branchName=repo.get("defaultBranch"),
                    ).get("branch")
                    codecommit.create_branch(
                        repositoryName=self.repository_name,
                        branchName=self.branch_name,
                        commitId=default_branch.get("commitId"),
                    )
                    codecommit.create_commit(
                        repositoryName=self.repository_name,
                        branchName=self.branch_name,
                        putFiles=files,
                        parentCommitId=default_branch.get("commitId"),
                    )
            else:
                codecommit.create_commit(
                    repositoryName=self.repository_name,
                    branchName=self.branch_name,
                    putFiles=files,
                )
