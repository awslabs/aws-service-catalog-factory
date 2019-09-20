Terraform Support
=================

Service Catalog Factory includes support for HashiCorp's Terraform.



What is working
---------------
- Provision your Terraform based products using ServiceCatalog Puppet
- Sharing Terraform based products using ServiceCatalog Puppet portfolio sharing
- Using Parameters in ServiceCatalog Puppet
- Using SSM Parameters in ServiceCatalog Puppet


Getting it working
------------------
- you need to add the following product set to your portfolio: https://github.com/awslabs/aws-service-catalog-products/tree/master/aws-servicecatalog-factory-provisioners
- you need to provision the products in aws-servicecatalog-factory-provisioners into your spoke accounts where you will be provisioning Terraform based products
- you can then create products.  Your products need to have their terraform code in a directory named tf.

.. note::

    This was added in version 0.13.0 and the syntax changed in 0.14.0

To create a Terraform based product you must set the product versions provisioner to Terraform:

.. code-block:: yaml

    Versions:
        - Active: true
          Description: The iam roles needed for you to do your jobs
          Name: v1
          Provisioner:
            Type: Terraform
            Version: 0.11.14
            TFVars:
              - Foo
              - Bar
          Source:
            Configuration:
              BranchName: v1
              RepositoryName: account-iam-terraform
            Provider: CodeCommit

You can choose which version of Terraform is used to provision your product.  The valid options are listed `here <https://releases.hashicorp.com/terraform/>`_

The TFVars you specify are exposed as parameters when using AWS Service Catalog (meaning you can set them using parameters in AWS Service Catalog Puppet) .


How does it work
----------------
When you specify a product uses a Terraform provisioner the framework will generate an AWS CloudFormation template with the following resources:
- an AWS S3 bucket that will be used to store the state
- an AWS CodePipeline containing AWS CodeBuild steps that download and run a Terraform plan and apply
- when you provision a Terraform based product the bucket and pipeline are provisioned into the account and the resources defined in the Terraform code are provisioned


What is still to come
---------------------
- Using Depends On in ServiceCatalog Puppet where you can depend on a Terraform based product
- Using Outputs in ServiceCatalog Puppet for a Terraform based product