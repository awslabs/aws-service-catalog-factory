Designing your products
=======================

Your products are AWS Service Catalog Products and so you are confined to the conventions of Service Catalog.

Product Versions
----------------
In Service Catalog, each product has one or more versions.  Versions represent changes to your products.  When you make 
a change to a published product it is recommended to make a new version and make it available to your users. 
  
Users can provision multiple versions of your product at the same time or they may choose to update a product from one 
version to another.  It is good to communicate to your users whether you would like them to update a product or provision
a new product when you issue a change.

Product Right-Sizing
--------------------
Right-sizing your product is difficult.  Try to create products that achieve a business outcome and that can be deployed
independently.  If something is reusable try to make it independent using AWS SSM Parameters or exporting the values from
the AWS CloudFormation templates.

Including your product in multiple portfolios
---------------------------------------------

.. note::

    This was added in version 0.2.0

You may want to include a product in more than one portfolio.  This is possible with aws-service-catalog-factory.  To do
this you must specify the product in a Products attribute at the root of the portfolio:

.. code-block:: yaml

    Schema: factory-2019-04-01

    Products:
      - Name: account-iam-standalone
        Owner: central-it@customer.com
        Description: The iam roles needed for you to do your jobs
        Distributor: central-it-team
        SupportDescription: Contact us on Chime for help #central-it-team
        SupportEmail: central-it-team@customer.com
        SupportUrl: https://wiki.customer.com/central-it-team/self-service/account-iam
        Portfolios:
          - central-it-team-portfolio
          - my-other-portfolio
        Tags:
          - Key: product-type
            Value: iam
        Versions:
          - Name: v1
            Description: The iam roles needed for you to do your jobs
            Active: True
            Source:
              Provider: CodeCommit
              Configuration:
                RepositoryName: account-iam
                BranchName: v1



Adding associations to a portfolio
----------------------------------

Within the products specification you can list the portfolios it should be associated with.  The values for the portfolios
should be the display name of the portfolio as specified in the portfolio file:


.. code-block:: yaml

    Schema: factory-2019-04-01

    Products:
      - Name: account-iam-standalone
        ...
        Portfolios:
          - my-other-portfolio
        Versions:
          - Name: v1
            Description: The iam roles needed for you to do your jobs
            Active: True
            Source:
              Provider: CodeCommit
              Configuration:
                RepositoryName: account-iam
                BranchName: v1
    Portfolios:
      - DisplayName: my-other-portfolio
        Description: A place for self service products ready for your account
        ProviderName: central-it-team
        ...


Adding launch role constraints to a product
-------------------------------------------

.. note::

    This was added in version 0.39.0

Within the product specification you can also specify a LocalRoleName for a LaunchRoleConstraint:

.. code-block:: yaml

    Schema: factory-2019-04-01

    Products:
      - Name: account-iam-standalone
        Owner: central-it@customer.com
        Distributor: central-it-team
        Constraints:
            Launch:
                LocalRoleName: ServiceCatalogLaunchRole

