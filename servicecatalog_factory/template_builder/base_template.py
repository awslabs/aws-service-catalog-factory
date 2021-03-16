SOURCE_OUTPUT_ARTIFACT = "Source"
BUILD_OUTPUT_ARTIFACT = "Build"


class BaseTemplate(object):
    def render(self, product_ids_by_region, tags) -> str:
        return ""
