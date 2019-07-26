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
