Terraform Support
=================

Service Catalog Factory includes support for HashiCorp's Terraform.

.. note::

    This was added in version 0.13.0 and the syntax changed in 0.14.0

You can now specify the provisioner for a product version:

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
- you can then create products.  Your products need to have their terraform code in a directory named tf but that is the only limitation.

What is still to come
---------------------
- Using Depends On in ServiceCatalog Puppet where you can depend on a Terraform based product
- Using Outputs in ServiceCatalog Puppet for a Terraform based product