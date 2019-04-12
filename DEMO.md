# HOW TO RUN A DEMO

# Install the tool
```bash
pip install aws-service-catalog-factory==0.1.14
```
# Bootstrap your account
```bash
servicecatalog-factory bootstrap 0.1.14
```

# Set up your factory
```bash
git clone --config 'credential.helper=!aws codecommit credential-helper $@' --config 'credential.UseHttpPath=true' https://git-codecommit.eu-west-1.amazonaws.com/v1/repos/ServiceCatalogFactory
servicecatalog-factory seed simple ServiceCatalogFactory
cd ServiceCatalogFactory
git add .
git commit -am "initial add"
git push
```

# Setup your first product
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
