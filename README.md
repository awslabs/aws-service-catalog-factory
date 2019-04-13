## servicecatalog-factory

![logo](./docs/logo.png) 

This is a framework where you define a Service Catalog portfolio, products and versions using YAML. For versions of your 
products you specify where the source code for them can be found and the framework publishes the portfolio, products and 
versions in every* AWS Region after validating, linting and testing them.

### High level architecture diagram

![whatisthis](./docs/whatisthis.png)

You build products in a central hub account using AWS CodePipeline and AWS CodeBuild, you then deploy them into AWS 
Service Catalog in every enabled region of your hub account using AWS CodePipeline and AWS CloudFormation. 

## Getting started

Follow the steps below to get started:

### Install the tool
Optional, but recommended:
```bash
virtualenv --python=python3.7 venv
source venv/bin/activate
```

Install the package:
```bash
pip install aws-service-catalog-factory
```

### Bootstrap your account
Create the AWS CodeCommit repo and AWS CodePipeline resources to run the factory:
```bash
servicecatalog-factory bootstrap
```

### Setup your factory
Clone the configuration repo and configure your factory:
```bash
git clone --config 'credential.helper=!aws codecommit credential-helper $@' --config 'credential.UseHttpPath=true' https://git-codecommit.eu-west-1.amazonaws.com/v1/repos/ServiceCatalogFactory
servicecatalog-factory seed simple ServiceCatalogFactory
cd ServiceCatalogFactory
git add .
git commit -am "initial add"
git push
```
Wait for pipeline to complete and you have a working factory.

### Setup your first product
Create your first product in your account:
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
Wait for the product pipeline to complete and you have a Service Catalog product ready to deploy in each region of your
account.


## License

This library is licensed under the Apache 2.0 License. 
