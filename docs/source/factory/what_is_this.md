What is this? 
=============

This is a framework where you define a Service Catalog portfolio, products and
versions using YAML. For versions of your products you specify where the source
code for them can be found and the framework publishes the portfolio, products
and versions in every* AWS Region after validating, linting and testing them.

## High level architecture diagram

![](./whatisthis.png)

You build products in a central hub account using AWS CodePipeline and AWS CodeBuild, you then deploy them into AWS 
Service Catalog in every enabled region of your hub account using AWS CodePipeline and AWS CloudFormation. 


## Providing your factory to multiple accounts - hub and spoke model

If you would like to share your Factory and its contents with other accounts, it is recommended you create a Factory 
Account within your organization.  This would be considered a _hub_ account.  This framework can be installed into 
many accounts within the same AWS Organization - meaning you can have multiple factory accounts.

 
![](./hub.png)

You can use your Factory to provide AWS Service Catalog products to your _spoke_ accounts.  You can even use the factory
to build the content in other hub accounts (including the account hosting your factory).