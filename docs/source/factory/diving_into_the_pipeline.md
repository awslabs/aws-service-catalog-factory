Diving into the pipelines
=========================

Each Product version in your portfolio becomes a CodePipeline in your Factory account.  At a minimum, each pipeline has
the following stages:

## Source
The source for your pipeline can be a CodeCommit repo or a GitHub repo.  
### Using CodeCommit 
To use CodeCommit you can use the following
configuration:
```yaml
Source:
    Provider: CodeCommit
    Configuration:
        RepositoryName: account-iam
        BranchName: v1
```
### Using GitHub 
To use GitHub you can use the following
configuration:
```yaml
Source:
    Provider: GitHub
    Configuration:
        Owner: your-github-user-or-org
        Repo: your-github-repo
        Branch: v1
```

Your pipeline will expect a JSON secret in AWS Secrets Manager of the name:
```<portfolio_file_name>-<portfolio_display_name>-<product_name>_<product_version_name>```

For example if you have the following in a file named example-simple.yaml:
```yaml
Portfolios:
  - DisplayName: central-it-team-portfolio
    Components:
      - Name: account-iam
        Versions:
          - Name: v1
            Source:
              Provider: Github
              Configuration:
                Owner: eamonnfaherty
                Repo: account-iam
                Branch: v1
```
The secret must be named: ```example-simple-central-it-team-portfolio-account-iam-v1``` and must have secret keys 
for ```SecretToken``` and ```OAuthToken```.  Please note it must be in the same region as the AWS CodePipeline.

## Tests
Each product pipeline will run aws cloudformation validate-template on your product.template.yaml.
You can optionally run CFNNag on your template.  You can enable it using the Options configuration for your product or
for your product version.

### Specifying the options at a product level
You can add CFN for all versions of a product:
```yaml
Portfolios:
  - 
    Components:
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
``` 

### Specifying the options at a version level
You can add CFN for a specific version of a product:
```yaml
Portfolios:
  - 
    Components:
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

``` 
## Package
By default, the BuildSpec for the AWS CodeBuild project used at the package stage will run the following for each region:
```bash
aws cloudformation package --template $(pwd)/product.template.yaml --s3-bucket sc-factory-artifacts-${ACCOUNT_ID}-{{ region }} --s3-prefix ${STACK_NAME} --output-template-file product.template-{{ region }}.yaml
``` 
This allows you to use AWS CloudFormation transform statements within your products meaning you can use AWS::Serverless::Function and other 
AWS CloudFormation types.

You can override this behaviour be making a change to your product version, adding a BuildSpec string:
```yaml
        Versions:
          - Name: v1
            Description: MVP for iam development account.
            Source:
              Provider: CodeCommit
              Configuration:
                RepositoryName: guardduty-master-enabler
                BranchName: v1
            BuildSpec: |
              version: 0.2
              phases:
                build:
                  commands:
                  {% for region in ALL_REGIONS %}
                    - aws cloudformation package --template $(pwd)/product.template.yaml --s3-bucket sc-factory-artifacts-${ACCOUNT_ID}-{{ region }} --s3-prefix ${STACK_NAME} --output-template-file product.template-{{ region }}.yaml
                  {% endfor %}
              artifacts:
                files:
                  - '*'
                  - '**/*'
```
Please note, when using this your BuildSpec will be rendered as a Jinja2 template with the following variables available
in the context:
- product
- version
- ALL_REGIONS

If you do decide to override the default build spec please ensure you capture the artifacts needed for the deploy stage.

## Deploy
The deploy stage will push your templates into AWS Service Catalog for each region you are opperating in.  The deploy
stage will look for files matching:
```product.template-{{ region }}.yaml```


## Setting versions to be active or not 
From the portfolio you can set a version to be active or not using the following syntax:
```yaml
    Components:
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
```
You set Versions[].Active to False to stop users from provisioning your product version.

Please note the ```servicecatalog-factory-pipeline``` updates the active setting.  If you find the value is not in sync 
run the pipeline. 