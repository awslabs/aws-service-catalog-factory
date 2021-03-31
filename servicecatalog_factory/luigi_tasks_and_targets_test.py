from unittest import skip
from . import tasks_unit_tests_helper


class GetBucketTaskTest(tasks_unit_tests_helper.FactoryTaskUnitTest):
    region = "region"

    def setUp(self) -> None:
        from servicecatalog_factory import luigi_tasks_and_targets

        self.module = luigi_tasks_and_targets

        self.sut = self.module.GetBucketTask(region=self.region)

        self.wire_up_mocks()

    def test_params_for_results_display(self):
        # setup
        expected_result = {
            "region": self.region,
        }

        # exercise
        actual_result = self.sut.params_for_results_display()

        # verify
        self.assertEqual(expected_result, actual_result)

    @skip
    def test_run(self):
        # setup
        # exercise
        actual_result = self.sut.run()

        # verify
        raise NotImplementedError()


class CreatePortfolioTaskTest(tasks_unit_tests_helper.FactoryTaskUnitTest):
    region = "region"
    portfolio_group_name = "ccoe"
    display_name = "self-service"
    description = "portfolio for sharing"
    provider_name = "ccoe"
    tags = []

    def setUp(self) -> None:
        from servicecatalog_factory import luigi_tasks_and_targets

        self.module = luigi_tasks_and_targets

        self.sut = self.module.CreatePortfolioTask(
            region=self.region,
            portfolio_group_name=self.portfolio_group_name,
            display_name=self.display_name,
            description=self.description,
            provider_name=self.provider_name,
            tags=self.tags,
        )

        self.wire_up_mocks()

    def test_params_for_results_display(self):
        # setup
        expected_result = {
            "region": self.region,
            "portfolio_group_name": self.portfolio_group_name,
            "display_name": self.display_name,
        }

        # exercise
        actual_result = self.sut.params_for_results_display()

        # verify
        self.assertEqual(expected_result, actual_result)

    @skip
    def test_run(self):
        # setup
        # exercise
        actual_result = self.sut.run()

        # verify
        raise NotImplementedError()


class CreatePortfolioAssociationTaskTest(tasks_unit_tests_helper.FactoryTaskUnitTest):
    region = "region"
    portfolio_group_name = "ccoe"
    display_name = "self-service"
    description = "portfolio for sharing"
    provider_name = "ccoe"
    tags = []
    associations = []
    factory_version = ""

    def setUp(self) -> None:
        from servicecatalog_factory import luigi_tasks_and_targets

        self.module = luigi_tasks_and_targets

        self.sut = self.module.CreatePortfolioAssociationTask(
            region=self.region,
            portfolio_group_name=self.portfolio_group_name,
            display_name=self.display_name,
            description=self.description,
            provider_name=self.provider_name,
            tags=self.tags,
            associations=self.associations,
            factory_version=self.factory_version,
        )

        self.wire_up_mocks()

    @skip
    def test_requires(self):
        # setup
        # exercise
        actual_result = self.sut.requires()

        # verify
        raise NotImplementedError()

    def test_params_for_results_display(self):
        # setup
        expected_result = {
            "region": self.region,
            "portfolio_group_name": self.portfolio_group_name,
            "display_name": self.display_name,
        }

        # exercise
        actual_result = self.sut.params_for_results_display()

        # verify
        self.assertEqual(expected_result, actual_result)

    @skip
    def test_run(self):
        # setup
        # exercise
        actual_result = self.sut.run()

        # verify
        raise NotImplementedError()


class CreateProductTaskTest(tasks_unit_tests_helper.FactoryTaskUnitTest):
    uid = ""
    region = "region"
    name = "name"
    owner = ""
    description = "portfolio for sharing"
    distributor = "ccoe"
    support_description = "contact us"
    support_email = "someone@somewhere.com"
    support_url = "https://wiki"
    tags = []

    def setUp(self) -> None:
        from servicecatalog_factory import luigi_tasks_and_targets

        self.module = luigi_tasks_and_targets

        self.sut = self.module.CreateProductTask(
            uid=self.uid,
            region=self.region,
            name=self.name,
            owner=self.owner,
            description=self.description,
            distributor=self.distributor,
            support_description=self.support_description,
            support_email=self.support_email,
            support_url=self.support_url,
            tags=self.tags,
        )

        self.wire_up_mocks()

    def test_params_for_results_display(self):
        # setup
        expected_result = {
            "region": self.region,
            "uid": self.uid,
            "name": self.name,
        }

        # exercise
        actual_result = self.sut.params_for_results_display()

        # verify
        self.assertEqual(expected_result, actual_result)

    @skip
    def test_requires(self):
        # setup
        # exercise
        actual_result = self.sut.requires()

        # verify
        raise NotImplementedError()

    @skip
    def test_run(self):
        # setup
        # exercise
        actual_result = self.sut.run()

        # verify
        raise NotImplementedError()


class DeleteProductTaskTest(tasks_unit_tests_helper.FactoryTaskUnitTest):
    uid = ""
    region = "region"
    name = "name"
    pipeline_mode = "combined"

    def setUp(self) -> None:
        from servicecatalog_factory import luigi_tasks_and_targets

        self.module = luigi_tasks_and_targets

        self.sut = self.module.DeleteProductTask(
            uid=self.uid,
            region=self.region,
            name=self.name,
            pipeline_mode=self.pipeline_mode,
        )

        self.wire_up_mocks()

    def test_params_for_results_display(self):
        # setup
        expected_result = {
            "region": self.region,
            "uid": self.uid,
            "name": self.name,
            "pipeline_mode": self.pipeline_mode,
        }

        # exercise
        actual_result = self.sut.params_for_results_display()

        # verify
        self.assertEqual(expected_result, actual_result)

    @skip
    def test_run(self):
        # setup
        # exercise
        actual_result = self.sut.run()

        # verify
        raise NotImplementedError()


class AssociateProductWithPortfolioTaskTest(
    tasks_unit_tests_helper.FactoryTaskUnitTest
):
    region = "region"
    portfolio_args = dict(portfolio_group_name="ccoe",)
    product_args = dict(name="DeleteDefaultVPC",)

    def setUp(self) -> None:
        from servicecatalog_factory import luigi_tasks_and_targets

        self.module = luigi_tasks_and_targets

        self.sut = self.module.AssociateProductWithPortfolioTask(
            region=self.region,
            portfolio_args=self.portfolio_args,
            product_args=self.product_args,
        )

        self.wire_up_mocks()

    def test_params_for_results_display(self):
        # setup
        expected_result = {
            "region": self.region,
            "portfolio": f"{self.portfolio_args.get('portfolio_group_name')}-{self.portfolio_args.get('display_name')}",
            "product": self.product_args.get("name"),
        }

        # exercise
        actual_result = self.sut.params_for_results_display()

        # verify
        self.assertEqual(expected_result, actual_result)

    @skip
    def test_requires(self):
        # setup
        # exercise
        actual_result = self.sut.requires()

        # verify
        raise NotImplementedError()

    @skip
    def test_run(self):
        # setup
        # exercise
        actual_result = self.sut.run()

        # verify
        raise NotImplementedError()


class EnsureProductVersionDetailsCorrectTest(
    tasks_unit_tests_helper.FactoryTaskUnitTest
):
    region = "region"
    version = {}
    product_args = dict(name="Delete-Default-VPC")

    def setUp(self) -> None:
        from servicecatalog_factory import luigi_tasks_and_targets

        self.module = luigi_tasks_and_targets

        self.sut = self.module.EnsureProductVersionDetailsCorrect(
            region=self.region, version=self.version, product_args=self.product_args
        )

        self.wire_up_mocks()

    def test_params_for_results_display(self):
        # setup
        expected_result = {
            "region": self.region,
            "version": self.version.get("Name"),
            "product": self.product_args.get("name"),
        }

        # exercise
        actual_result = self.sut.params_for_results_display()

        # verify
        self.assertEqual(expected_result, actual_result)

    @skip
    def test_requires(self):
        # setup
        # exercise
        actual_result = self.sut.requires()

        # verify
        raise NotImplementedError()

    @skip
    def test_run(self):
        # setup
        # exercise
        actual_result = self.sut.run()

        # verify
        raise NotImplementedError()


class CreateVersionPipelineTemplateTaskTest(
    tasks_unit_tests_helper.FactoryTaskUnitTest
):
    all_regions = None
    version = {}
    product = {}
    provisioner = dict(Type="CloudFormation",)
    template = None
    factory_version = ""
    products_args_by_region = None
    tags = []

    def setUp(self) -> None:
        from servicecatalog_factory import luigi_tasks_and_targets

        self.module = luigi_tasks_and_targets

        self.sut = self.module.CreateVersionPipelineTemplateTask(
            all_regions=self.all_regions,
            version=self.version,
            product=self.product,
            provisioner=self.provisioner,
            template=self.template,
            factory_version=self.factory_version,
            products_args_by_region=self.products_args_by_region,
            tags=self.tags,
        )

        self.wire_up_mocks()

    def test_params_for_results_display(self):
        # setup
        expected_result = {
            "version": self.version.get("Name"),
            "product": self.product.get("Name"),
            "type": self.provisioner.get("Type"),
        }

        # exercise
        actual_result = self.sut.params_for_results_display()

        # verify
        self.assertEqual(expected_result, actual_result)

    @skip
    def test_requires(self):
        # setup
        # exercise
        actual_result = self.sut.requires()

        # verify
        raise NotImplementedError()

    @skip
    def test_run(self):
        # setup
        # exercise
        actual_result = self.sut.run()

        # verify
        raise NotImplementedError()


class CreateVersionPipelineTaskTest(tasks_unit_tests_helper.FactoryTaskUnitTest):
    all_regions = None
    version = {}
    product = {}
    provisioner = None
    template = None
    products_args_by_region = None
    factory_version = ""
    region = "region"
    tags = []

    def setUp(self) -> None:
        from servicecatalog_factory import luigi_tasks_and_targets

        self.module = luigi_tasks_and_targets

        self.sut = self.module.CreateVersionPipelineTask(
            all_regions=self.all_regions,
            version=self.version,
            product=self.product,
            provisioner=self.provisioner,
            template=self.template,
            products_args_by_region=self.products_args_by_region,
            factory_version=self.factory_version,
            region=self.region,
            tags=self.tags,
        )

        self.wire_up_mocks()

    def test_params_for_results_display(self):
        # setup
        expected_result = {
            "version": self.version.get("Name"),
            "product": self.product.get("Name"),
        }

        # exercise
        actual_result = self.sut.params_for_results_display()

        # verify
        self.assertEqual(expected_result, actual_result)

    @skip
    def test_requires(self):
        # setup
        # exercise
        actual_result = self.sut.requires()

        # verify
        raise NotImplementedError()

    @skip
    def test_run(self):
        # setup
        # exercise
        actual_result = self.sut.run()

        # verify
        raise NotImplementedError()


class DeleteAVersionTaskTest(tasks_unit_tests_helper.FactoryTaskUnitTest):
    product_args = dict(uid="unique",)
    version = "{}"

    def setUp(self) -> None:
        from servicecatalog_factory import luigi_tasks_and_targets

        self.module = luigi_tasks_and_targets

        self.sut = self.module.DeleteAVersionTask(
            product_args=self.product_args, version=self.version
        )

        self.wire_up_mocks()

    def test_params_for_results_display(self):
        # setup
        expected_result = {
            "uid": self.product_args.get("uid"),
            "region": self.product_args.get("region"),
            "name": self.product_args.get("name"),
            "version": self.version,
        }

        # exercise
        actual_result = self.sut.params_for_results_display()

        # verify
        self.assertEqual(expected_result, actual_result)

    @skip
    def test_requires(self):
        # setup
        # exercise
        actual_result = self.sut.requires()

        # verify
        raise NotImplementedError()

    @skip
    def test_run(self):
        # setup
        # exercise
        actual_result = self.sut.run()

        # verify
        raise NotImplementedError()


class CreateCombinedProductPipelineTemplateTaskTest(
    tasks_unit_tests_helper.FactoryTaskUnitTest
):
    all_regions = None
    product = {}
    products_args_by_region = None
    factory_version = ""

    def setUp(self) -> None:
        from servicecatalog_factory import luigi_tasks_and_targets

        self.module = luigi_tasks_and_targets

        self.sut = self.module.CreateCombinedProductPipelineTemplateTask(
            all_regions=self.all_regions,
            product=self.product,
            products_args_by_region=self.products_args_by_region,
            factory_version=self.factory_version,
        )

        self.wire_up_mocks()

    def test_params_for_results_display(self):
        # setup
        expected_result = {
            "product": self.product.get("Name"),
        }

        # exercise
        actual_result = self.sut.params_for_results_display()

        # verify
        self.assertEqual(expected_result, actual_result)

    @skip
    def test_requires(self):
        # setup
        # exercise
        actual_result = self.sut.requires()

        # verify
        raise NotImplementedError()

    @skip
    def test_run(self):
        # setup
        # exercise
        actual_result = self.sut.run()

        # verify
        raise NotImplementedError()


class CreateCombinedProductPipelineTaskTest(
    tasks_unit_tests_helper.FactoryTaskUnitTest
):
    all_regions = None
    product = {}
    products_args_by_region = None
    factory_version = ""

    def setUp(self) -> None:
        from servicecatalog_factory import luigi_tasks_and_targets

        self.module = luigi_tasks_and_targets

        self.sut = self.module.CreateCombinedProductPipelineTask(
            all_regions=self.all_regions,
            product=self.product,
            products_args_by_region=self.products_args_by_region,
            factory_version=self.factory_version,
        )

        self.wire_up_mocks()

    def test_params_for_results_display(self):
        # setup
        expected_result = {
            "product": self.product.get("Name"),
        }

        # exercise
        actual_result = self.sut.params_for_results_display()

        # verify
        self.assertEqual(expected_result, actual_result)

    @skip
    def test_requires(self):
        # setup
        # exercise
        actual_result = self.sut.requires()

        # verify
        raise NotImplementedError()

    @skip
    def test_run(self):
        # setup
        # exercise
        actual_result = self.sut.run()

        # verify
        raise NotImplementedError()
