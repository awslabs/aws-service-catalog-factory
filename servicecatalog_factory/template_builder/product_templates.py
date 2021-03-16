import troposphere as t

from servicecatalog_factory.template_builder.cdk import shared_resources

def get_template() -> t.Template:
    description = "todo"
    tpl = t.Template(Description=description)

    for resource in shared_resources.resources:
        tpl.add_resource(
            resource
        )

    return tpl
