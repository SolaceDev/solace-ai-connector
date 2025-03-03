Overview:

We are about to add the concept of 'apps' in this project.
An 'app' (short for application) is a collection of flows that are logically grouped together.
This will allow you to run multiple apps in the same connector instance, each with their own configuration.
In the configuration, there will be a new key called `apps` that will contain a list of apps.
Each app will have its own configuration, including the flows that are part of the app.
This change must be backward compatible with the current configuration format, so for configurations
that do not have the `apps` key, an app will be created to contain the flows in that configuration. If
the configuration came from a .yaml file, then the app name will be the name of the file without the extension.
If there are multiple files, then each file will be a separate app. 
There will be a new App class that will contain the flows and the configuration for the app.
This may be inherited by custom apps to add additional functionality and configurations.
Configuration for the app will be specified in a similar way to how it is done for components. The App class
will only have a few required fields, such as the name of the app and the flows that are part of the app and the num_instances, for
cases where the app is running multiple instances. The App class will also have a method to start the app, which will start all the flows in the app.
When components call "get_config" the component_base will first check its own configuration for the key, and if it is not found, it will check the app configuration.

Remember that it is crucial that this change is backward compatible with the current configuration format.

Implementation plan:

<inst>
fill this section in for the impementation steps for adding apps
</inst>