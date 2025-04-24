# Adding a simplified mode for apps 

We are adding a new mode of running an app that would make it much simpler to build a simple app that is basically one component. 

We will define an app without any flows and just have configuration for the app that define how it will interact with Solace brokers. In its config, there will be a broker config that contains the usual SOLACE_ config and it will also contain input_enabled, output_enabled and request_reply_enabled. For request_reply, it is indicating that during processing it may need to send a request to a broker and wait for a reply. 

The app will automatically create a flows similar to what would be done now where it can receive from the broker and send to the broker. The app will be able to specify a queue name and a list of subscriptions. Each subscription can have an optional component that will be called when a message is received matching that subscription.  

input_enabled will indicate that the app will receive messages from the broker. It will create a flow to receive messages from the broker and send them to the app input queue. The app can then process these messages in its own way.
output_enabled will indicate that the app will send messages to the broker. It will create a flow to send messages from the app output queue to the broker. The app can then send messages to the broker in its own way.
request_reply_enabled will indicate that the app will send messages to the broker and wait for a reply. Part of this will be creating a dedicated response queue with a subscription to the response topic. 

This will be worked into the existing app framework and will be a new mode of running an app. Care should be taken to make the configuration as clean and simple as possible. When the app is running, it should behave very similarly to how it does now, but the app developer will not have to worry about creating flows or managing them. 

## Clarifying questions

1.  **Processing Logic Definition:**
    *   How will the user define the core processing logic for a simplified app? Will it be a reference to a standard component (like `invoke`, `llm_chat`), a Python function, a script path, or something else?
    - We will need to use a component for this. The configuration would take an optional component within the subscription definition for it to send its messages to. 
    *   If it's a component, how are its specific configuration parameters provided within the simplified app structure?
    - Components, through the get_config method would be able to get the config for the app as they do today.

    - We might want to consider an easier way to define a component that can more easily provide the input and output schemas, etc. For very simple apps, it would be nice to just have a small file that can define everything the app needs, including the component it uses, etc.

    - Additionally, for the configuration, it should be possible to code all of this into the app itself. Much of it is code specific, so we shouldn't have to code the behaviour in one place and then have the yaml agree with it. For example, often the subscriptions used are known a coding time and having them in the yaml might actually break things if it is changed.


2.  **Configuration Structure:**
    *   Could you provide an example YAML snippet showing the proposed structure for a simplified app definition, including broker details, queue/subscription definitions, interaction flags (`input_enabled`, etc.), and the processing logic reference?
    - Note that there would only be one queue for the app, which simplifies the receive message handling since it is a synchronous call.
    - The app config would look like this:
    ```yaml
    app:
      name: my_simplified_app
      broker:
        host: <broker_host>
        port: <broker_port>
        username: <username>
        password: <password>
        input_enabled: true
        output_enabled: true
        request_reply_enabled: true
        queue_name: <queue_name>
      config:
        # Optional app-specific configuration
        param1: value1
        param2: value2
      components:
        - name: <component_name>
          <normal component config>
          subscriptions:
            - topic: <topic1>
            qos: 1
            queue_name: <queue1>
            - topic: <topic2>
            qos: 1
        - name: <component_name>
          <normal component config>
          subscriptions:
            - topic: <topic3>
            qos: 1
            queue_name: <queue2>
    ```
    - We should be able to define all of this within the app code itself. A simple app might have a single file that defines a simple component at the top with a basic invoke method. The app would be created with hardcoded configuration for the broker and the component. The app would then be able to run a very minimal yaml file.

3.  **Broker Interaction Flags (`input_enabled`, `output_enabled`, `request_reply_enabled`):**
    *   `input_enabled`: Does this imply the framework implicitly creates and manages a dedicated `BrokerInput` component instance for this app, listening on the specified queue?
    - yes
    *   `output_enabled`: Does this imply a dedicated `BrokerOutput` instance? How does the app's processing logic trigger sending a message (e.g., returning a specific structure, calling a framework-provided function)?
    - In the app class, there should be a method that can be called to send a message, however, normally the return value of the component will be used to send the message.
    *   `request_reply_enabled`: Does this imply a dedicated `BrokerRequestResponse` instance? Is the simplified app acting as the *requester* or the *responder*? How does the app logic initiate a request or formulate a reply?
    - yes. For this we are the requester. It would use the request reply stuff that is in the base component. In the simplified app we would use the same broker config for input/output and request reply. 

4.  **Shared vs. Dedicated Broker Components:**
    *   Based on our discussion, the preference seems to be for implicitly creating *dedicated* broker components (`BrokerInput`, `BrokerOutput`, `BrokerRequestResponse`) per simplified app instance rather than shared ones. Can we confirm this is the intended approach to maintain isolation and simplify acknowledgement/error handling?
    - yes, we will keep them separate

5.  **Queue/Subscription Management:**
    *   Will the framework *always* attempt to create the specified queues and add subscriptions (`create_queue_on_start=True` behavior), or will this be configurable?
    - this should be configurable. The default should be to create the queues and subscriptions.
    *   What happens if the connector lacks the necessary SEMP permissions to create queues/subscriptions?
    - We are creating the queues through the data connection, so this should not be a problem.
    *   How should conflicts be handled if two different simplified app definitions specify the same queue name?
    - Allow this and if the broker allows it, it will go ahead. If not we will throw an error. This is no different than what we do now.

6.  **Error Handling:**
    *   How are exceptions raised within the app's processing logic handled? Will they trigger a NACK back to the broker (if applicable)? Will they be sent to the main error queue?
    - this should be the same as what we do now
    *   How are broker connection errors handled for the implicitly created components? Will reconnections be attempted based on the app's broker config?
    - yes, we will use the same reconnection logic as we do now.

7.  **Output Mechanism Details:**
    *   If `output_enabled` is true, what specific mechanism will the app's processing logic use to specify the payload, topic, and user properties of the message to be sent? (e.g., return a dict `{"payload": ..., "topic": ..., "user_properties": ...}`?)
    - yes, this is the same as what we do now. The app will have a way to send a message which will take a dict with the payload, topic, and user properties and it will create the message and send it to the broker.

8.  **Invocation Context:**
    *   When a message arrives (`input_enabled`), what context/data structure is passed to the app's processing logic? Is it the standard `Message` object?
    - yes, this is the same as what we do now. 

9.  **Integration and Coexistence:**
    *   Can these simplified apps run within the same `SolaceAiConnector` instance alongside standard apps defined with explicit flows?
    - yes, this must work

10. **Lifecycle and Scalability:**
    *   How are simplified apps started/stopped? Is it tied to the main connector lifecycle?
    - yes, this is the same as what we do now
    *   Will there be a way to run multiple instances of the same simplified app definition (similar to `num_instances` for flows/components)? If so, how is naming/identification handled?
    - we should support num_instances. This should only increase the number of components in the middle of the flow. The app itself will not be duplicated. This means there is one broker input and one broker output, but multiple components in the middle.


## Thoughts on Answers to Questions

<inst>
Fill in your thoughts now that you see the answers to the questions. Ask more questions if you have them.
</inst>

