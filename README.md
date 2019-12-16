# aws-service-catalog-factory

![logo](./docs/logo.png) 

## What is it?
This is a python3 framework that makes it easier to build multi region AWS Service Catalog portfolios.

With this framework you define a portfolio in YAML.  For each product version in your portfolio you specify which git 
repository it is in and the framework will build out AWS CodePipelines for each product version.

These CodePipelines can run CFN_NAG and Cloudformation_rspec on your templates enabling you to check your templates are 
good quality that they are functionally correct.

## Getting started

You can read the [installation how to](https://service-catalog-tools-workshop.com/30-how-tos/10-installation/20-service-catalog-factory.html)
or you can read through the [every day use](https://service-catalog-tools-workshop.com/30-how-tos/50-every-day-use.html)
guides.

You can read the [documentation](https://aws-service-catalog-factory.readthedocs.io/en/latest/) to understand the inner 
workings. 


## Going further

The framework is one of a pair.  The other is [aws-service-catalog-puppet](https://github.com/awslabs/aws-service-catalog-puppet).
With Service Catalog Puppet you can provision products into multiple regions of multiple accounts using YAML and you can 
share portfolios across multiple regions of multiple accounts. 

## License

This library is licensed under the Apache 2.0 License. 
