Getting it up and running
=========================

ServiceCatalog-Factory runs in your AWS Account.  In order for you to install it into your account you can use the 
aws-service-catalog-factory cli.  This is distributed via [PyPi](https://pypi.org/project/aws-service-catalog-factory/)

What am I going to install?
---------------------------
---------------------------
ServiceCatalog-Factory is bootstrapped from your local machine.  You install a command line utility that will provision
the resources you need into your AWS Account.  Once you have completed the bootstrap you will have the following pipeline
in your account:


.. image:: ./factory-getting-started-what-am-i-going-to-install-pipeline.png

using the following services:

.. image:: ./factory-getting-started-what-am-i-going-to-install.png



Before you install
------------------
You should consider which account will be the home for your factory.  This account will contain the AWS CodePipelines
and will need to be accessible to any accounts you would like to share with.


Installing the tool
-------------------

Bootstrapping the Factory
+++++++++++++++++++++++++

Installing the framework into your AWS account is easy.  You will need to log into the console and then navigate to the
AWS CloudFormation service in the region you want to create your Service Catalog portfolios pipelines.

From there you need to select ``Create stack``.  Ensure you have selected ``Template is ready`` from the ``Prerequisite - Prepare template``
options and then you will need to select ``Amazon S3 URL`` from the ``Specify template`` options.  There should be an
input field titled ``Amazon S3 URL`` in which you should paste:

.. code-block::

    https://service-catalog-tools.s3.eu-west-2.amazonaws.com/factory/latest/servicecatalog-factory-initialiser.template.yaml

Once you have pasted the URL hit ``Next``.  You will be asked to enter a ``Stack name``.  We recommend the name:
``servicecatalog-factory-initialiser``.

One the same screen you will prompted to set the parameters.  Below is explanation of the parameters you can configure:

- EnabledRegions: the framework will create Service Catalog portfolios in each of the specified regions.

When you have set the value for your parameters hit ``Next``, review the next screen, scroll down and hit ``Next`` again.
Review the final ``Review`` screen, scroll to the bottom, check the box labeled ``I acknowledge that AWS CloudFormation
might create IAM resources with custom names.`` and then finally hit ``Create Stack``.

Configuring your factory
++++++++++++++++++++++++

You now need to configure your factory.  You can clone the repo or edit it in the AWS Console.

Cloning the repo
~~~~~~~~~~~~~~~~

You now need to clone the configuration repo and configure your factory.  To get the url of the repo look at the
``servicecatalog-factory-initialiser`` outputs.  If you want to clone via SSH then you can use the value of
``ServiceCatalogFactoryRepoCloneURLSSH`` or if you want to clone via HTTPS then you can use the value of
``ServiceCatalogFactoryRepoCloneURLHTTPS``.  Replace the url in the snippet below to get your clone working:

.. code-block:: bash

    git clone \
        --config 'credential.helper=!aws codecommit credential-helper $@' \
        --config 'credential.UseHttpPath=true' \
        https://git-codecommit.eu-west-1.amazonaws.com/v1/repos/ServiceCatalogFactory
    servicecatalog-factory seed simple ServiceCatalogFactory
    cd ServiceCatalogFactory
    git add .
    git commit -am "initial add"
    git push


For Windows users, use git clone command as:

.. code-block:: bash

    git clone \
        --config "credential.helper=!aws codecommit credential-helper $@" \
        --config "credential.UseHttpPath=true" \
        https://git-codecommit.eu-west-1.amazonaws.com/v1/repos/ServiceCatalogFactory


If you would like to get started with a sample setup you can use the seed command.  The seed command takes two parameters.
The first is the name of the example file you would like to use.  At the moment here is only a _simple_ option. You can
also specify a simple github see using:

.. code-block:: bash

    servicecatalog-factory seed simple-github ServiceCatalogFactory


More will be coming soon to show the flexibility of the Factory.

Once the pipeline has completed you have a working factory!  You will now need to configure at least one product.


Editing in the AWS Console
~~~~~~~~~~~~~~~~~~~~~~~~~~

If you do not like using git you can build your portfolios directly in the AWS Console.  To get started to go the
``ServiceCatalogFactory`` git repo.  This will be in CodeCommit in the region you created your pipelines in.  The URL for
the page in the console is available as a clickable output from the ``servicecatalog-factory-initialiser`` stack named
``ServiceCatalogFactoryRepoConsoleURL``.

Once you are in your ``ServiceCatalogFactory`` repo you will need to create a new directory in the master branch named
``portfolios``.  Within that directory you will need to create a YAML file to store your portfolio.  That file should have
the extension ``.yaml``. Please create the file and read the building your pipelines section to get started.


Setting up a product
++++++++++++++++++++
The simple example file you used in the previous step declared an account-iam product that is stored in CodeCommit.
For the product pipeline to work you will need to create the git repo and add the product.template.yaml.

You can use the following snippet to do this easily:

.. code-block:: bash

    aws codecommit create-repository --repository-name account-iam
    git clone --config 'credential.helper=!aws codecommit credential-helper $@' --config 'credential.UseHttpPath=true' https://git-codecommit.eu-west-1.amazonaws.com/v1/repos/account-iam
    cd account-iam
    curl https://raw.githubusercontent.com/eamonnfaherty/cloudformation-templates/master/iam_admin_role/product.template.yaml -o product.template.yaml
    git checkout -b v1
    git add .
    git commit -am "initial add"
    git push --set-upstream origin v1

For Windows users, use git clone command as:

.. code-block:: bash

    git clone --config "credential.helper=!aws codecommit credential-helper $@" --config "credential.UseHttpPath=true" https://git-codecommit.eu-west-1.amazonaws.com/v1/repos/account-iam


Please note, this clone command also contains an AWS Region that may need to change for this action to work.

Once you have pushed your product.template.yaml file you and the product pipeline has completed and you have a Service 
Catalog product ready to deploy in each region of your account.
