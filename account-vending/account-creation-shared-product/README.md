# product.template
# Description
Lambda for backing custom resources to create an AWS Account


## Parameters
The list of parameters for this template:

### AssumableOrgRoleArn 
Type: AWS::SSM::Parameter::Value<String> 
Default: AssumableOrgRole 
Description: IAM role to assume that enables Organizations access to create and move the cereated account 

## Resources
The list of resources this template creates:

### AccountCustomResourceRole 
Type: AWS::IAM::Role  
### AccountCustomResource 
Type: AWS::Serverless::Function 
Description: The lambda function that creates an account when called using a CloudFormation Custom Resource:
```yaml
Account:
  Type: Custom::CustomResource
  Description: A custom resource representing an AWS Account
  Properties:
    ServiceToken: !Ref AccountVendingCreationLambda
    Email: !Ref Email
    AccountName: !Ref AccountName
    OrganizationAccountAccessRole: !Ref OrganizationAccountAccessRole
    IamUserAccessToBilling: !Ref IamUserAccessToBilling
    TargetOU: !Ref TargetOU
```
 
### Param 
Type: AWS::SSM::Parameter 
Description: Outputs the AccountCustomResource Arn to an SSM param named ```account-vending-creation-lambda```
 

## Outputs
The list of outputs this template exposes:

### AccountId 
  

