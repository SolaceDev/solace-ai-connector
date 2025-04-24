# Adding a simplified mode for apps 

We are adding a new mode of running an app that would make it much simpler to build a simple app that is basically one component. 

We will define an app without any flows and just have configuration for the app that define how it will interact with Solace brokers. In its config, there will be a broker config that contains the usual SOLACE_ config and it will also contain input_enabled, output_enabled and request_reply_enabled. For request_reply, it is indicating that during processing it may need to send a request to a broker and wait for a reply. 

The app will automatically create a flows similar to what would be done now where it can receive from the broker and send to the broker. The app will be able to specify a queue name and a list of subscriptions. Each subscription can have an optional 'invoke method' that will be called when a message is received matching that subscription.  

input_enabled will indicate that the app will receive messages from the broker. It will create a flow to receive messages from the broker and send them to the app input queue. The app can then process these messages in its own way.
output_enabled will indicate that the app will send messages to the broker. It will create a flow to send messages from the app output queue to the broker. The app can then send messages to the broker in its own way.
request_reply_enabled will indicate that the app will send messages to the broker and wait for a reply. Part of this will be creating a dedicated response queue with a subscription to the response topic. 

This will be worked into the existing app framework and will be a new mode of running an app. Care should be taken to make the configuration as clean and simple as possible. When the app is running, it should behave very similarly to how it does now, but the app developer will not have to worry about creating flows or managing them. 

## Clarifying questions

<inst>
Fill this in with a list of questions that need to be answered before starting the work.
</inst>

