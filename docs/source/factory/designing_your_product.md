Designing your products
=======================

Your products are AWS Service Catalog Products and so you are confined to the conventions of Service Catalog.

## Product Versions
In Service Catalog, each product has one or more versions.  A consumer of your products will be able to provision each
version of each product you provide but there are limitations.  You cannot share resources between the AWS Service
Catalog product versions - for example if you create an IAM Policy in version one of a product you will not be able to
modify it in version two.  Version two will have its own resources independent of version ones resources.

Given this, the recommended approach is to make incremental changes to a product within the same version.  Versions are
useful to provide alternative ways of achieving the same goal - for example you may want a networking product that has a
transit-vpc version, a transit-gateway version or a standalone version.

## Product Right-Sizing
Right-sizing your product is difficult.  Try to create products that achieve a business outcome and that can be deployed
independently.  If something is reusable try to make it independent using AWS SSM Parameters or exporting the values from
the AWS CloudFormation templates.