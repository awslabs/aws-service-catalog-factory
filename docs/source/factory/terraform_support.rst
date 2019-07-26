Terraform Support
=================

Service Catalog Factory includes *experimental support* for HashiCorp's Terraform.

.. note::

    This was added in version 0.13.0

You can now specify a product version type:

.. code-block:: yaml

    Versions:
        - Active: true
          Description: The iam roles needed for you to do your jobs
          Name: v1
          Type: Terraform
          Source:
            Configuration:
              BranchName: v1
              RepositoryName: account-iam-terraform
            Provider: CodeCommit

.. warning::

    THIS IS EXPERIMENTAL.  This is not guaranteed to be backwards compatible.


What is working
---------------
- Provision your Terraform based products using ServiceCatalog Puppet
- Sharing Terraform based products using ServiceCatalog Puppet portfolio sharing
- Using Parameters in ServiceCatalog Puppet
- Using SSM Parameters in ServiceCatalog Puppet


What is still to come
---------------------
- Using Depends On in ServiceCatalog Puppet
- Using Outputs in ServiceCatalog Puppet