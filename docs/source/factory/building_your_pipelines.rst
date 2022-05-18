Building your pipelines
=======================

You write portfolio files that contain products and their versions.

Each Product version in your portfolio becomes a CodePipeline in your Factory account.

For each product version you must specify the following:

Source
------
The source for your pipeline can be a CodeCommit repo or a GitHub repo.  


Using AWS CodeCommit
++++++++++++++++++++

See https://service-catalog-tools-workshop.com/every-day-use/100-creating-a-product/300-add-the-source-code.html


Using Amazon S3
+++++++++++++++

See https://service-catalog-tools-workshop.com/every-day-use/100-creating-a-product/310-creating-s3-pipelines.html


Using GitHub
++++++++++++

See https://service-catalog-tools-workshop.com/every-day-use/100-creating-a-product/305-creating-codestar-pipelines.html


Using CodeStarSourceConnection (Bitbucket / Github.com / Github Enterprise)
+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

See https://service-catalog-tools-workshop.com/every-day-use/100-creating-a-product/305-creating-codestar-pipelines.html


Preprocessing templates (using Jinja2)
--------------------------------------

.. note::

    ShouldParseAsJinja2Template was added in version 0.20.0

When you write your product.template.yaml file you can use Jinja2 to optimise the way you write your CloudFormation
template.  To enable this you must specify the ``ShouldParseAsJinja2Template`` option and your product.template.yaml
file must be renamed product.template.yaml.j2

Here is an example showing the option turned on:

.. code-block:: yaml

    Portfolios:
      -
        Products:
          - Name: account-iam
            Options:
              ShouldParseAsJinja2Template: True
            Versions:
              - Name: v1
                Description: IAM Policies needed
                Source:
                  Provider: CodeCommit
                  Configuration:
                    RepositoryName: development-account-networking
                    BranchName: v1



Using JSON
----------
By default factory assumes you will be using YAML based CloudFormation templates.  You can use JSON based products by
changing the provisioning configuration for CloudFormation:

.. code-block:: yaml

    Products:
      - Name: json-product
        Portfolios:
          - mandatory
        Versions:
          - Name: v1
            Provisioner:
              Type: CloudFormation
              Format: json
            Source:
              Configuration:
                BranchName: master
                RepositoryName: aws-iam-administrator-access-assumable-role-account
              Provider: CodeCommit
            Tags:
              - Key: provider
                Value: central-it-team

Please note the example above is not complete, it is just illustrating how to set a provisioner.

.. note::

    ShouldParseAsJinja2Template was added in version 0.35.0




Build
-----

.. note::

    This was added in version 0.48.0

Each product pipeline can have a build stage.  You can specify the BuildSpecImage and the BuildSpec to use by setting
the Build properties in the Stages object:

.. code:: yaml

    Products:
      - Description: account-bootstrap-shared
        Distributor: CCOE
        Name: account-bootstrap-shared
        Owner: CCOE@Example.com
        Source:
          Configuration:
            RepositoryName: account-bootstrap-shared
          Provider: CodeCommit
        Stages:
          Build:
            BuildSpecImage: aws/codebuild/standard:4.0
            BuildSpec: |
              version: 0.2
              phases:
                install:
                  runtime-versions:
                    python: 3.x
                build:
                  commands:
                    - make build
              artifacts:
                files:
                  - '*'
                  - '**/*'

        SupportDescription: Find us on Slack or Wiki
        SupportEmail: ccoe-support@Example.com
        SupportUrl: https://example.com/intranet/teams/ccoe/products/account-factory
        Tags: []
        Portfolios:
          - account-vending
        Versions:
          - Description: Creates, codebuild project that can be run to bootstrap an account
              and lambda function that can be used to back a custom resource so the codebuild
              project can be started from CloudFormation
            Name: v1

In the example above we added a BuildSpecImage and a BuildSpec.  You cal also override the stages object in the versions
list:

.. code:: yaml

    Products:
      - Description: account-bootstrap-shared
        Distributor: CCOE
        Name: account-bootstrap-shared
        Owner: CCOE@Example.com
        Source:
          Configuration:
            RepositoryName: account-bootstrap-shared
          Provider: CodeCommit

        SupportDescription: Find us on Slack or Wiki
        SupportEmail: ccoe-support@Example.com
        SupportUrl: https://example.com/intranet/teams/ccoe/products/account-factory
        Tags: []
        Portfolios:
          - account-vending
        Versions:
          - Description: Creates, codebuild project that can be run to bootstrap an account
              and lambda function that can be used to back a custom resource so the codebuild
              project can be started from CloudFormation
            Name: v1
            Stages:
              Build:
                BuildSpecImage: aws/codebuild/standard:4.0
                BuildSpec: |
                  version: 0.2
                  phases:
                    install:
                      runtime-versions:
                        python: 3.x
                    build:
                      commands:
                        - make build
                  artifacts:
                    files:
                      - '*'
                      - '**/*'

Please note you cannot set a build stage for a combined pipeline.

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

    aws cloudformation package \
        --template $(pwd)/product.template.yaml \
        --s3-bucket sc-factory-artifacts-${ACCOUNT_ID}-{{ region }} \
        --s3-prefix ${STACK_NAME} \
        --output-template-file \
        product.template-{{ region }}.yaml

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
            Stages:
              Package:
                BuildSpec: |
                  version: 0.2
                  phases:
                    install:
                      runtime-versions:
                        python: 3.8
                    build:
                      commands:
                      {% for region in ALL_REGIONS %}
                        - aws cloudformation package \
                            --template $(pwd)/product.template.yaml \
                            --s3-bucket sc-factory-artifacts-${ACCOUNT_ID}-{{ region }} \
                            --s3-prefix ${STACK_NAME} \
                            --output-template-file product.template-{{ region }}.yaml
                      {% endfor %}
                  artifacts:
                    files:
                      - '*'
                      - '**/*'

.. note::

    Since version 0.48.0 you should be setting your Package BuildSpec in a Stages object unless using a combined
    pipeline.  Prior to this you set it in the versions or product object.  The stages object can be set in the product
    object and then overridden in the version object.


Please note, you need to specify the runtime-versions you intend to use.

Please note, when using this your BuildSpec will be rendered as a Jinja2 template with the following variables available
in the context:
- product
- version
- ALL_REGIONS

If you do decide to override the default build spec please ensure you capture the artifacts needed for the deploy stage.

The default image used for the Package stage of the pipeline is ```aws/codebuild/standard:4.0```.
To choose the image, add a BuildSpecImage configuration to either the product or version.

.. code-block:: yaml

        Versions:
          - Name: v1
            Description: MVP for iam development account.
            BuildSpecImage: aws/codebuild/standard:4.0
            BuildSpec: |
              mybuildspec...


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

Specifying versions of a component and/or products outside of the main portfolio file
---------------------------------------------------------------------

You may find that your portfolio file increases in size fairly quickly.  Having a large file to manage is often more
complicated than having multiple, smaller files.  If you find yourself in this situation you can provide the 
specification for component versions outside of your main portfolio file.

**For example:**

You have a portfolio file named ``demo.yaml`` under your ``portfolios`` directory.

In ``demo.yaml`` you define a portfolio named ``central-it-team-portfolio`` under the ``Portfolios`` section and a component/product named ``account-vending-account-creation`` under the ``Products`` section:

.. code-block:: yaml

    Schema: factory-2019-04-01
    Portfolios:
      - DisplayName: central-it-team-portfolio
        Description: A place for self service products ready for your account
        ProviderName: central-it-team
        Associations:
          - arn:aws:iam::${AWS::AccountId}:role/Admin
        Products:
          - Name: account-vending-account-creation
            Owner: central-it@customer.com
            Description: template used to interact with custom resources in the shared projects
            Distributor: central-it-team
            SupportDescription: Contact us on Chime for help #central-it-team

For Products
++++++++++++
As well as specifying your ``Products`` section for the product in the portfolio file, you can specify it as a product file within a directory structure which matches the flow of the manifest file using the following syntax:

  - ``/portfolios/<name_of_manifest_without.yaml>/Portfolios/<DisplayName_of_portfolio>/Products/<name_of_product>/<name of the product>.yaml``

**For example:**
To specify a product called ``product-a`` under the Products section of the ``central-it-team-portfolio`` portfolio defined in the 'demo.yaml' file, you can create a directory named in the following way:

  - ``/portfolios/demo/Portfolios/central-it-team-portfolio/Products/product-a/``

And a product file like:

  - ``/portfolios/demo/Portfolios/central-it-team-portfolio/Products/product-a/product-a.yaml``

With the Content:

.. code-block:: yaml

    Owner: central-it@customer.com
    Description: template used to interact with custom resources in the shared projects
    Distributor: central-it-team
    SupportDescription: Contact us on Chime for help #central-it-team

The Product name is taken from the filename of the product - this should also match the product folder name

  .. note:: You can put products in files or in the portfolio file

For Versions
++++++++++++
Rather than specifying your ``Versions`` section for the component/product, you can specify it in a specifications file within a directory structure which matches the flow of the manifest file using the following syntax:

  - ``/portfolios/<name_of_manifest_without.yaml>/Portfolios/<DisplayName_of_portfolio>/Products/<name_of_product>/Versions``

  .. note:: You can alternatively use 'Components' instead of 'Products'

**For example:**

To specify the Versions section of the ``account-vending-account-creation`` defined in the 'demo.yaml' file, you can create a directory named in one of the following two ways:

  - ``/portfolios/demo/Portfolios/central-it-team-portfolio/Components/account-vending-account-creation/Versions/``
  - ``/portfolios/demo/Portfolios/central-it-team-portfolio/Products/account-vending-account-creation/Versions/``

.. note::  

  - You create this structure within the root of your ``ServiceCatalogFactory`` repository. 
  - The ``demo.yaml`` file should already be under the ``/portfolios`` folder.

Under the ``Versions`` folder, you can now create a folder for each version of your component/product which you place a ``specification.yaml`` file which contains the relevant version information:

.. code-block:: bash

    # tree .
    .
    ├── v1
    │   └── specification.yaml
    └── v2
        └── specification.yaml

    2 directories, 2 files


The files named ``specification.yaml`` need to contain the details for the version:

.. code-block:: yaml

    Description: template used to interact with custom resources in the shared projects.
    Active: True
    Source:
      Provider: CodeCommit
      Configuration:
        RepositoryName: account-vending-account-creation
        BranchName: master


**Example of the full folder structure:**

Folder Structure for above examples should look like this under ``ServiceCatalogFactory``

.. code-block:: bash

    # tree .

    .
    └── portfolios
        ├── demo
        │   └── Portfolios
        │       └── central-it-team-portfolio
        │           └── Products
        │               └── account-vending-account-creation
        │                   └── Versions
        │                       ├── v1
        │                       │   └── specification.yaml
        │                       └── v2
        │                           └── specification.yaml
        │               └── account-vending-account-creation.yaml
        └── demo.yaml

    9 directories, 4 files


When your service-catalog-factory pipeline runs it will treat these versions as if they were defined within the portfolio file.

Reducing the number of pipelines
--------------------------------
By default factory will create an AWS CodePipeline for each product version you specify.  By specifying a different
PipelineMode you can alter this behaviour:

.. code-block:: yaml

    Products:
      - Description: iam-assume-roles-spoke product
        Distributor: central-it-team
        Name: aws-iam-assume-roles-spoke
        Owner: central-it@customer.com
        SupportDescription: Contact us on Chime for help
        SupportEmail: central-it-team@customer.com
        SupportUrl: https://wiki.customer.com/central-it-team/self-service/account-iam
        PipelineMode: combined
        Portfolios:
          - combined


When you specify a combined pipeline mode only a single pipeline will be created.  There will be a source for each
version of your product.  When the pipeline runs only the changed product version will be updated in AWS Service
Catalog.  You can only set PipelineMode for products that you define outside of portfolios and you can only specify a
buildspec for the product and not the versions.