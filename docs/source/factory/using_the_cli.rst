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

    This was added in version 0.5.0

You can use the ``servicecatalog-factory`` cli to list all the AWS CodePipelines in your factory along with their status

.. code-block:: bash

    servicecatalog-factory show-pipelines ServiceCatalogFactory/portfolios


Will return the following:

.. code-block:: bash

    ┌─────────────────────────────────────────────────────────────────────────┬───────────┬──────────────────────────────────────────┬─────────────────────┐
    │ Pipeline                                                                │ Status    │ Last Commit Hash                         │ Last Commit Message │
    ├─────────────────────────────────────────────────────────────────────────┼───────────┼──────────────────────────────────────────┼─────────────────────┤
    │ servicecatalog-factory-pipeline                                         │ Succeeded │ 277c695b72d8d77ba0876e8bdf3ac2d48f2f5e15 │ fixing indent       │
    │ example-simple-github-central-it-team-portfolio-account-iam-v1-pipeline │ Failed    │ N/A                                      │ N/A                 │
    │ account-iam-soc-2-1-v1-pipeline                                         │ Failed    │ N/A                                      │ N/A                 │
    └─────────────────────────────────────────────────────────────────────────┴───────────┴──────────────────────────────────────────┴─────────────────────┘

.. note::

    This was added in version 0.11.0

You can specify the output format for show-pipelines.  Valid options are ``table`` and ``json``

.. code-block:: bash

    servicecatalog-factory show-pipelines ServiceCatalogFactory/portfolios --format json

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
