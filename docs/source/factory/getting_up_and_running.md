Getting it up and running
=========================

ServiceCatalog-Factory runs in your AWS Account.  In order for you to install it into your account you can use the 
aws-service-catalog-factory cli.  This is distributed via [PyPi](https://pypi.org/project/aws-service-catalog-factory/)

## Before you install
You should consider which account will be the home for your factory.  This account will contain the AWS CodePipelines
and will need to be accessible to any accounts you would like to share with.
 

## Installing the tool
This is a python cli built using Python 3.

It is good practice to install Python libraries in isolated environments.  You can create the a virtual environment using
the following command:

```bash
virtualenv --python=python3.7 venv
source venv/bin/activate
```

Once you have decided where to install the library you can install the package:
```bash
pip install aws-service-catalog-factory
```

This will install the library and all of the dependencies.


## Setting it up
The Factory will run in your account and needs some configuration.  You will need to stand up the factory and set up the 
configuration for it to run smoothly.


### Bootstrapping the Factory
Use the cli tool to create the AWS CodeCommit repo and AWS CodePipeline resources that run the factory:
```bash
servicecatalog-factory bootstrap
```
This command will take a little while to run.  Once the command completes you can move onto the next step.


### Configuring your factory
You now need to clone the configuration repo and configure your factory:
```bash
git clone --config 'credential.helper=!aws codecommit credential-helper $@' --config 'credential.UseHttpPath=true' https://git-codecommit.eu-west-1.amazonaws.com/v1/repos/ServiceCatalogFactory
servicecatalog-factory seed simple ServiceCatalogFactory
cd ServiceCatalogFactory
git add .
git commit -am "initial add"
git push
```
Please note ```git clone``` command above includes an AWS Region in it.  You may need to change this or you can use the
command the bootstrap command prints to the terminal upon completion for the correct command.

The seed command takes two parameters.  The first is the name of the example file you would like to use.  At the moment
here is only a _simple_ option.  More will be coming soon to show the flexibility of the Factory.

Once the pipeline has completed you have a working factory!  You will now need to configure at least one product.

### Setup your first product
The simple example file you used in the previous step declared an account-iam product that is stored in CodeCommit.
For the product pipeline to work you will need to create the git repo and add the product.template.yaml.

You can use the following snippet to do this easily:

```bash
aws codecommit create-repository --repository-name account-iam
git clone --config 'credential.helper=!aws codecommit credential-helper $@' --config 'credential.UseHttpPath=true' https://git-codecommit.eu-west-1.amazonaws.com/v1/repos/account-iam
cd account-iam
curl https://raw.githubusercontent.com/eamonnfaherty/cloudformation-templates/master/iam_admin_role/product.template.yaml -o product.template.yaml
git checkout -b v1
git add .
git commit -am "initial add"
git push --set-upstream origin v1
```

Please note, this clone command also contains an AWS Region that may need to change for this action to work.

Once you have pushed your product.template.yaml file you and the product pipeline has completed and you have a Service 
Catalog product ready to deploy in each region of your account.