# org-bootstrap.template
# Description
IAM Role needed to use AWS Organizations to create AWS Accounts.

## Parameters
The list of parameters for this template:

### ServiceCatalogFactoryAccountId 
Type: String   

## Resources
The list of resources this template creates:

### AssumableOrgRole 
Type: AWS::IAM::Role 
Description: IAM Role needed by the account vending machine so it can create and move accounts
 
### AssumableOrgRoleParam 
Type: AWS::SSM::Parameter 
Description: SSM Parameter to help sharing of the AssumableOrgRole Arn.  Stores it in the SSM Param with the name
```AssumableOrgRole```
 

## Outputs
The list of outputs this template exposes:

### AssumableOrgRoleArn 
  

