Using the CLI
=============

When you install ``aws-service-catalog-factory`` you install a command line tool ``servicecatalog-factory``.

When you bootstrap the framework and upgrade it you use the cli tool to perform these actions.

There are other commands that you may find useful:

validate
--------

You can use the ``servicecatalog-factory`` cli to validate your portfolio yaml files:

.. code-block:: bash

    servicecatalog-factory validate portfolios/


add-secret
----------

.. note::

    This was added in version 0.17.0

You can use the ``servicecatalog-factory`` cli to add Secret Key and OAuth tokens that can be used to create products
where the source code comes from a GitHub Repo.

.. code-block:: bash


    servicecatalog-factory add-secret <secret-name> <oauth_token> <secret_token>

If you do not specify an secret token your oauth token will be used.  You should do this if you are using personal
access tokens.


add-product-to-portfolio
------------------------

.. note::

    This was added in version 0.9.0

You can use the ``servicecatalog-factory`` cli to add products into your portfolio.  This will add your product to the
remote version of the portfolio file you specify:

.. code-block:: bash

    servicecatalog-factory add-product-to-portfolio portfolio_file_name portfolio_display_name product_definition_file.yaml

product_definition_file.yaml should be a yaml file in the following format:

.. code-block:: yaml

    Description: The iam roles needed for you to do your jobs
    Distributor: central-it-team
    Name: account-iam-2
    Owner: central-it@customer.com
    SupportDescription: Contact us on Chime for help
    SupportEmail: central-it-team@customer.com
    SupportUrl: https://wiki.customer.com/central-it-team/self-service/account-iam
    Tags:
    - Key: product-type
      Value: iam

.. note::

    If your ``product_definition_file.yaml`` file contains a source which is CodeCommit then the repo will be created for you.


remove-product-from-portfolio
-----------------------------

.. note::

    This was added in version 0.9.0

You can use the ``servicecatalog-factory`` cli to remove products from your portfolio.  This will remove your product
from the remote version of the portfolio file you specify:

.. code-block:: bash

    servicecatalog-factory remove-product-from-portfolio portfolio_file_name portfolio_display_name product_name


.. note::

    This command will not delete git repos


add-version-to-product
----------------------

.. note::

    This was added in version 0.9.0

You can use the ``servicecatalog-factory`` cli to add versions to your products.  This will add your version to the
specified product in the remote version of the portfolio file you specify:

.. code-block:: bash

    servicecatalog-factory add-version-to-product example-simple.yaml central-it-team-portfolio account-iam-2 version_definition_file.yaml

version_definition_file.yaml should be a yaml file in the following format:

.. code-block:: yaml

    Name: v1
    Description: The iam roles needed for you to do your jobs
    Active: true
    Source:
      Provider: CodeCommit
      Configuration:
        BranchName: v1
        RepositoryName: account-iam

.. note::

    If your ``version_definition_file.yaml`` file contains a source which is CodeCommit then the repo will be created for you.


remove-version-from-product
---------------------------

.. note::

    This was added in version 0.9.0

You can use the ``servicecatalog-factory`` cli to remove versions from products in your portfolio.  This will remove
your version from your product in the remote version of the portfolio file you specify:

.. code-block:: bash

    servicecatalog-factory remove-version-from-product portfolio_file_name portfolio_display_name product_name version_name


.. note::

    This command will not delete git repos


import-product-set
------------------

.. note::

    This was added in version 0.8.0

You can use the ``servicecatalog-factory`` cli to import products from the aws-service-catalog-products shared repo.

This will update your portfolio file, create your AWS CodeCommit repos, export the code from the AWS shared code repo and
push the code into your AWS CodeCommit repo on the correct branch.

.. code-block:: bash

    servicecatalog-factory import-product-set ServiceCatalogFactory/portfolios/example-simple-github.yaml aws-iam central-it-team-portfolio

You must specify the path to the portfolio file you want to add the product set to, the name of the product set and the name
of the portfolio you want to add it to.


list-resources
--------------

.. note::

    This was added in version 0.7.0

You can use the ``servicecatalog-factory`` cli to list all the resources that will be created to bootstrap the framework

.. code-block:: bash

    servicecatalog-factory list-resources


Will return the following markdown:

.. code-block:: bash

    # Framework resources
    ## SSM Parameters used
    - /servicecatalog-factory/config
    ## Resources for stack: servicecatalog-factory-regional
    ┌────────────────────────┬─────────────────────┬────────────────────────────────────────────────────────────────┐
    │ Logical Name           │ Resource Type       │ Name                                                           │
    ├────────────────────────┼─────────────────────┼────────────────────────────────────────────────────────────────┤
    │ Param                  │ AWS::SSM::Parameter │ service-catalog-factory-regional-version                       │
    │ PipelineArtifactBucket │ AWS::S3::Bucket     │ Fn::Sub: sc-factory-artifacts-${AWS::AccountId}-${AWS::Region} │
    │                        │                     │                                                                │
    └────────────────────────┴─────────────────────┴────────────────────────────────────────────────────────────────┘
    ## Resources for stack: servicecatalog-factory
    ┌───────────────────────────────┬─────────────────────────────┬──────────────────────────────────────┐
    │ Logical Name                  │ Resource Type               │ Name                                 │
    ├───────────────────────────────┼─────────────────────────────┼──────────────────────────────────────┤
    │ Param                         │ AWS::SSM::Parameter         │ service-catalog-factory-version      │
    │ SourceRole                    │ AWS::IAM::Role              │ SourceRole                           │
    │ CodeRepo                      │ AWS::CodeCommit::Repository │ ServiceCatalogFactory                │
    │ BuildRole                     │ AWS::IAM::Role              │ CodeRole                             │
    │ BuildProject                  │ AWS::CodeBuild::Project     │ servicecatalog-product-factory-build │
    │ CodePipelineTriggerRole       │ AWS::IAM::Role              │ CodePipelineTriggerRole              │
    │ PipelineRole                  │ AWS::IAM::Role              │ CodePipelineRole                     │
    │ FactoryPipelineArtifactBucket │ AWS::S3::Bucket             │ Not Specified                        │
    │ CatalogBucket                 │ AWS::S3::Bucket             │ Not Specified                        │
    │ Pipeline                      │ AWS::CodePipeline::Pipeline │ Fn::Sub: ${AWS::StackName}-pipeline  │
    │                               │                             │                                      │
    │ DeliverySourceRole            │ AWS::IAM::Role              │ DeliverySourceRole                   │
    │ DeliveryBuildRole             │ AWS::IAM::Role              │ DeliveryCodeRole                     │
    │ DeliveryPipelineRole          │ AWS::IAM::Role              │ DeliveryCodePipelineRole             │
    └───────────────────────────────┴─────────────────────────────┴──────────────────────────────────────┘
    AWS::StackName evaluates to servicecatalog-factory

show-pipelines
--------------

.. note::

    This was changed in version 0.70.0

You can use the ``servicecatalog-factory`` cli to list all the AWS CodePipelines in your factory along with their status

.. code-block:: bash

    servicecatalog-factory show-pipelines ServiceCatalogFactory


Will return the following:

.. code-block:: bash

    +------------+------------------------------------------------+--------------------------------------+----------------------------------+-----------+------------------------------------------+------------------------------------------------------------+----------------+-------------------------------------------------------+
    | Type       | Name                                           | Execution Id                         | Start Time                       | Status    | Last Commit Id                           | Last Commit Message                                        | Duration       | Trend                                                 |
    +------------+------------------------------------------------+--------------------------------------+----------------------------------+-----------+------------------------------------------+------------------------------------------------------------+----------------+-------------------------------------------------------+
    | core       | servicecatalog-factory-pipeline                | d435a6b7-cc21-442f-ae47-e2947ae56ce3 | 2021-09-02 12:54:07.136000+01:00 | Failed    | c765347e01a36514a1e2f4cce691fc51964005d1 | sdfsdf                                                     | 0:01:06.964000 | Failed, Failed, Succeeded, Succeeded, Failed          |
    | apps       | app--ssm-parameter-v2-pipeline                 | 6f556352-3354-4641-a78e-f95bfe262470 | 2021-08-03 14:38:44.429000+01:00 | Failed    | 95e272ad32858b2a2d263268dde8fc7ba0eb6cc1 | Added param.tf                                             | 0:01:10.692000 | Failed                                                |
    | portfolios | bug-demo-portfolio-cdk-support-iam-v2-pipeline | N/A                                  | 2021-11-03 19:43:28.612484       | N/A       | N/A                                      | N/A                                                        | 0:00:00        |                                                       |
    | portfolios | cdk-support-iam-v2-pipeline                    | 21cebf98-9dcb-4a10-85bd-d7e273f9eaf1 | 2021-09-02 12:34:28.904000+01:00 | Succeeded | 09705a6242cd67c6e46364a7e70ae3857a2e1c65 | sdsdsd                                                     | 0:01:48.474000 | Succeeded, Failed, Succeeded, Succeeded, Succeeded    |
    | portfolios | cdk-support-bootstrap-v4-pipeline              | 3740315e-f317-4d5b-baa2-1a022f22f6f4 | 2021-04-09 19:51:09.178000+01:00 | Succeeded | b38fe7fea05002e1e3d1f86f9454d8a5a64bbceb | Edited handler.py                                          | 0:02:47.400000 | Succeeded, Succeeded, Succeeded, Superseded, Failed   |
    | portfolios | cdk-ssm-parameter-single-stack-v1-pipeline     | c84c925a-ca04-4763-b430-8fa8c370e995 | 2021-04-09 19:24:09.927000+01:00 | Succeeded | aadb4ca8198c318f976c975df1c3d3ad62f1d84f | initial add                                                | 0:05:17.851000 | Succeeded, Succeeded, Failed, Failed, Failed          |
    |            |                                                |                                      |                                  |           |                                          |                                                            |                |                                                       |
    | portfolios | cdk-ssm-parameter-single-stack-v2-pipeline     | a9a289fe-55e5-44e1-8b5c-e73f003c0467 | 2021-05-07 16:34:45.587000+01:00 | Succeeded | 5509f682d2207e0439c16b7dc63deccdded86c44 | Edited cdk-ssm-parameter-single-stack-v1-pipeline-stack.ts | 0:05:17.644000 | Succeeded, Failed, Failed, Failed, Failed             |
    | portfolios | cdk-ssm-parameter-two-stacks-v1-pipeline       | ddd83a86-c10f-4031-b4bd-4c17e266561f | 2021-03-25 18:34:53.223000+00:00 | Failed    | N/A                                      | N/A                                                        | 0:00:01.293000 | Failed, Failed, Failed, Failed, Failed                |
    | portfolios | simpleproduct-v1-pipeline                      | 043bf8e6-154f-436f-9ef2-c0d19d2de57e | 2021-06-07 11:28:48.976000+01:00 | Failed    | N/A                                      | N/A                                                        | 0:00:01.734000 | Failed, Failed, Succeeded, Succeeded, Succeeded       |
    | portfolios | simpleproduct-suffixed-v1-pipeline             | 6cdcb202-dcc7-4c08-b8a7-a7b42d0cf2da | 2021-03-03 22:46:08.472000+00:00 | Failed    | N/A                                      | N/A                                                        | 0:00:01.247000 | Failed                                                |
    | stacks     | stack--ssm-parameter-v2-pipeline               | 7badb987-137d-4c3b-b773-3e0cc66b5782 | 2021-09-02 11:02:35.745000+01:00 | Succeeded | 467f87832e5330dbdac346ce823e5e0671b27435 | Added stack.template.yaml                                  | 0:02:22.555000 | Succeeded, Failed, Failed, Succeeded                  |
    | stacks     | stack--aac-type-b-network-v1-pipeline          | N/A                                  | 2021-11-03 19:43:28.612484       | N/A       | N/A                                      | N/A                                                        | 0:00:00        |                                                       |
    | workspaces | workspace--ssm-parameter-v2-pipeline           | e95b2731-5c8f-4a1c-a35e-430770e10783 | 2021-08-03 15:13:42.181000+01:00 | Succeeded | 64d866c7205f33266d85d7c99eb11f38f4ff99d2 | Edited param.tf                                            | 0:01:46.176000 | Succeeded, Succeeded, Succeeded, Succeeded, Succeeded |
    +------------+------------------------------------------------+--------------------------------------+----------------------------------+-----------+------------------------------------------+------------------------------------------------------------+----------------+-------------------------------------------------------+

.. note::

    This was added in version 0.11.0

You can specify the output format for show-pipelines.  Valid options are ``table``, ``json`` and ``html``

.. code-block:: bash

    servicecatalog-factory show-pipelines ServiceCatalogFactory/ --format json

nuke-product-version
--------------------
You can use the ``servicecatalog-factory`` cli to remove a product from AWS Service Catalog and to remove
the AWS CodePipeline that was generated by this library.  To use it, you will need your portofolio name,
product name and product version - all of which is available to view from your AWS Service Catalog console.

Once you have the details you can run the following command:

.. code-block:: bash

    servicecatalog-factory nuke-product-version example-simple-central-it-team-portfolio account-iam v1


delete-stack-from-all-regions
-----------------------------
You can delete a stack from every region using the following command:

.. code-block:: bash

    servicecatalog-factory delete-stack-from-all-regions stack-name

Please note, this will only delete the stack from the regions you have specifed in your config.


fix-issues
----------
Whilst developing your products you may find AWS CloudFormation stacks in states you cannot work with.  
If this happens the fix-issues command will try to resolve it for you.  It will prompt you to confirm
anything it does within your account before it does it so give it a try when you get stuck.

.. code-block:: bash

    servicecatalog-factory fix-issues ServiceCatalogFactory/portfolios
