Designing your products
=======================

Your products are AWS Service Catalog Products and so you are confined to the conventions of Service Catalog.

## Product Versions
In Service Catalog, each product has one or more versions.  Versions represent changes to your products.  When you make 
a change to a published product it is recommended to make a new version and make it available to your users. 
  
Users can provision multiple versions of your product at the same time or they may choose to update a product from one 
version to another.  It is good to communicate to your users whether you would like them to update a product or provision
a new product when you issue a change.

## Product Right-Sizing
Right-sizing your product is difficult.  Try to create products that achieve a business outcome and that can be deployed
independently.  If something is reusable try to make it independent using AWS SSM Parameters or exporting the values from
the AWS CloudFormation templates.