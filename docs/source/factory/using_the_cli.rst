Using the CLI
=============

When you install ``aws-service-catalog-factory`` you install a command line tool ``servicecatalog-factory``.

When you bootstrap the framework and upgrade it you use the cli tool to perform these actions.

There are other commands that you may find useful:

show-resources
--------------

.. note::

    This was added in version 0.7.0

You can use the ``servicecatalog-factory`` cli to list all the resources that will be created to bootstrap the framework

.. code-block:: bash

    servicecatalog-factory show-resources


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
