AWS CDK Support
===============

Service Catalog Factory includes support for preparing AWS CDK projects for provisioning or sharing using Service
Catalog Puppet.

This doc only addresses the use case of building AWS Service Catalog products comprising of AWS CDK source code that
will be shared using Service Catalog Puppet.

What is working
---------------
- Create a product using AWS CDK
- Provide parameters for your AWS CDK project using AWS CloudFormation parameters
- Capture outpouts for your AWS CDK Project using AWS CloudFormation stack outputs


Getting it working
------------------

Prerequisites
~~~~~~~~~~~~~

If you are building a service catalog of products comprising of AWS CDK projects you will need to run a CDK bootstrap
in each account you are sharing portolios with.  There is a helper product set that makes this easier for you:

https://github.com/awslabs/aws-service-catalog-products/tree/main/unsorted/cdk-support

You will need to provision the IAM product to each account only once and you can then provision the bootstrap product
to specific regions where you would like to run cdk bootstrap.  There are parameters on those products allowing you to
customise the cdk bootstrap arguements.

You can look at the example manifest file for an example of how you can provision the prerequisites.

Creating a CDK product pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To create a CDK product you will need a specialised pipeline that will create the wrapper AWS CloudFormation template
that will be added to AWS Service Catalog and copy the source code for later deploying.  In order to do this you can
use the following syntax within your Portfolios section:


.. code-block:: yaml

    Versions:
       -  Active: true
          Description: The iam roles needed for you to do your jobs
          Name: v1
          Template:
            Name: CDK
            Version: 1.0.0
          Source:
            Configuration:
              BranchName: v1
              RepositoryName: account-iam-cdk
            Provider: CodeCommit

Adding the Template attribute tells the solution the product being described will be an AWS CDK product and so the
specialised pipeline will be created.

If you need additional runtime-versions and commands to be run before the CDK deploy command is run you can specify
these like so:

.. code-block:: yaml

    Versions:
      - Name: "v1"
        Owner: "data-governance@example.com"
        Description: "Simple product"
        Distributor: "cloud-engineering"
        SupportDescription: "Speak to data-governance@example.com about exceptions and speak to cloud-engineering@example.com about implementation issues"
        SupportEmail: "cloud-engineering@example.com"
        SupportUrl: "https://wiki.example.com/cloud-engineering/governance/data-controls"
        Template:
          Name: CDK
          Version: 1.0.0
          Configuration:
            runtime-versions:
              python: 3.8
            install:
              commands:
                - pip install -r requirements.txt

Please note you can add multiple runtime-versions (it is a dictionary) and you can add multiple install commands (it is
a list).

The runtime-versions are added and the commands are executed in the hub account when the product template is being
created and in the spoke account when the CDK deploy is being executed.

Using the CDK based products
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Once you have generated the product you can use them in a launch - the parameters and outputs will work as if the project
was a plain old CloudFormation based product.  You can share the portfolio containing the CDK based product using the
normal spoke-local-portfolio method.
