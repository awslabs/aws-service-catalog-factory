SOURCE_OUTPUT_ARTIFACT = "Source"
BUILD_OUTPUT_ARTIFACT = "Build"
VALIDATE_OUTPUT_ARTIFACT = "Validate"
PACKAGE_OUTPUT_ARTIFACT = "Package"
DEPLOY_OUTPUT_ARTIFACT = "Deploy"


class BaseTemplate(object):
    def render(self, product_ids_by_region, tags) -> str:
        return ""