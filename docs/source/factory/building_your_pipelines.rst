Building your pipelines
=======================

You write portfolio files that contain products and their versions.

Each Product version in your portfolio becomes a CodePipeline in your Factory account.

For each product version you must specify the following:

Source
------
The source for your pipeline can be a CodeCommit repo or a GitHub repo.  

Using CodeCommit
++++++++++++++++

To use CodeCommit you can use the following
configuration:

.. code-block:: yaml

    Source:
        Provider: CodeCommit
        Configuration:
            RepositoryName: account-iam
            BranchName: v1


Using GitHub
++++++++++++

To use GitHub you can use the following
configuration:

.. code-block:: yaml

    Source:
        Provider: GitHub
        Configuration:
            Owner: your-github-user-or-org
            Repo: your-github-repo
            Branch: v1


Your pipeline will expect a JSON secret in AWS Secrets Manager of the name:
```<portfolio_file_name>-<portfolio_display_name>-<product_name>_<product_version_name>```

For example if you have the following in a file named example-simple.yaml:

.. code-block:: yaml

    Portfolios:
      - DisplayName: central-it-team-portfolio
        Products:
          - Name: account-iam
            Versions:
              - Name: v1
                Source:
                  Provider: Github
                  Configuration:
                    Owner: eamonnfaherty
                    Repo: account-iam
                    Branch: v1

The secret must be named: ```example-simple-central-it-team-portfolio-account-iam-v1``` and must have secret keys 
for ```SecretToken``` and ```OAuthToken```.  Please note it must be in the same region as the AWS CodePipeline.

Tests
-----
Each product pipeline will run aws cloudformation validate-template on your product.template.yaml.
You can optionally run CFNNag on your template.  You can enable it using the Options configuration for your product or
for your product version.

Specifying the options at a product level
+++++++++++++++++++++++++++++++++++++++++

You can add CFN for all versions of a product:

.. code-block:: yaml

    Portfolios:
      -
        Products:
          - Name: account-iam
            Options:
              ShouldCFNNag: True
            Versions:
              - Name: v1
                Description: IAM Policies needed
                Source:
                  Provider: CodeCommit
                  Configuration:
                    RepositoryName: development-account-networking
                    BranchName: v1


Specifying the options at a version level
+++++++++++++++++++++++++++++++++++++++++

You can add CFN for a specific version of a product:

.. code-block:: yaml

    Portfolios:
      -
        Products:
          - Name: account-iam
            Versions:
              - Name: v1
                Description: IAM Policies needed
                Options:
                  ShouldCFNNag: True
                Source:
                  Provider: CodeCommit
                  Configuration:
                    RepositoryName: development-account-networking
                    BranchName: v1


Package
-------

By default, the BuildSpec for the AWS CodeBuild project used at the package stage will run the following for each region:

.. code-block:: bash

    aws cloudformation package --template $(pwd)/product.template.yaml --s3-bucket sc-factory-artifacts-${ACCOUNT_ID}-{{ region }} --s3-prefix ${STACK_NAME} --output-template-file product.template-{{ region }}.yaml

This allows you to use AWS CloudFormation transform statements within your products meaning you can use AWS::Serverless::Function and other 
AWS CloudFormation types.

You can override this behaviour be making a change to your product version, adding a BuildSpec string:

.. code-block:: yaml

        Versions:
          - Name: v1
            Description: MVP for iam development account.
            Source:
              Provider: CodeCommit
              Configuration:
                RepositoryName: guardduty-master-enabler
                BranchName: v1
            BuildSpec: |
              version: 0.2
              phases:
                build:
                  commands:
                  {% for region in ALL_REGIONS %}
                    - aws cloudformation package --template $(pwd)/product.template.yaml --s3-bucket sc-factory-artifacts-${ACCOUNT_ID}-{{ region }} --s3-prefix ${STACK_NAME} --output-template-file product.template-{{ region }}.yaml
                  {% endfor %}
              artifacts:
                files:
                  - '*'
                  - '**/*'

Please note, when using this your BuildSpec will be rendered as a Jinja2 template with the following variables available
in the context:
- product
- version
- ALL_REGIONS

If you do decide to override the default build spec please ensure you capture the artifacts needed for the deploy stage.

Deploy
------

The deploy stage will push your templates into AWS Service Catalog for each region you are opperating in.  The deploy
stage will look for files matching:
```product.template-{{ region }}.yaml```


Setting versions to be active or not
------------------------------------

From the portfolio you can set a version to be active or not using the following syntax:

.. code-block:: yaml

    Products:
      - Name: account-vending-machine
        Owner: central-it@customer.com
        Description: The iam roles needed for you to do your jobs
        Distributor: central-it-team
        SupportDescription: Contact us on Chime for help #central-it-team
        SupportEmail: central-it-team@customer.com
        SupportUrl: https://wiki.customer.com/central-it-team/self-service/account-iam
        Tags:
        - Key: product-type
          Value: iam
        Versions:
          - Name: v1
            Description: The iam roles needed for you to do your jobs
            Active: False
            Source:
              Provider: CodeCommit
              Configuration:
                RepositoryName: account-vending-machine 
                BranchName: v1

You set Versions[].Active to False to stop users from provisioning your product version.

Please note the ```servicecatalog-factory-pipeline``` updates the active setting.  If you find the value is not in sync 
run the pipeline. 

Specifying versions of a component outside of the main portfolio file
---------------------------------------------------------------------

You may find that your portfolio file increases in size fairly quickly.  Having a large file to manage is often more
complicated than having multiple, smaller files.  If you find yourself in this situation you can provide the 
specification for component versions outside of your main portfolio file.

For example if you have a portfolio file named ``demo.yaml`` and it defines a portfolio named
``central-it-team-portfolio`` as this snippet shows:

.. code-block:: yaml

    Schema: factory-2019-04-01
    Portfolios:
      - DisplayName: central-it-team-portfolio
        Description: A place for self service products ready for your account
        ProviderName: central-it-team
        Associations:
          - arn:aws:iam::${AWS::AccountId}:role/Admin

and you have a component named ``account-vending-account-creation`` as this snippet shows:

.. code-block:: yaml

    Products:
      - Name: account-vending-account-creation
        Owner: central-it@customer.com
        Description: template used to interact with custom resources in the shared projects
        Distributor: central-it-team
        SupportDescription: Contact us on Chime for help #central-it-team
      
you can create a directory named 
``/portfolios/demo/Portfolios/central-it-team-portfolio/Components/account-vending-account-bootstrap-shared/Versions/``
or
``/portfolios/demo/Portfolios/central-it-team-portfolio/Products/account-vending-account-bootstrap-shared/Versions/``
within the root of your ``ServiceCatalogFactory`` repository and within that directory you can add sub directories for each
version you wish to define:

.. code-block:: bash

    # tree .
    .
    ├── v1
    │   └── specification.yaml
    └── v2
        └── specification.yaml

    2 directories, 2 files


The files named specification need to contain the details for the version:

.. code-block:: yaml

    Description: template used to interact with custom resources in the shared projects.
    Active: True
    Source:
      Provider: CodeCommit
      Configuration:
        RepositoryName: account-vending-account-creation
        BranchName: master


Please note, the name of the directory is used as the name of the version.

When your service-catalog-factory pipeline runs it will treat these versions as if they were defined within the portfolio 
file.