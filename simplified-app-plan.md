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
1.  **Processing Logic Definition:**
    *   How will the user define the core processing logic for a simplified app? Will it be a reference to a standard component (like `invoke`, `llm_chat`), a Python function, a script path, or something else?
    *   If it's a component, how are its specific configuration parameters provided within the simplified app structure?

2.  **Configuration Structure:**
    *   Could you provide an example YAML snippet showing the proposed structure for a simplified app definition, including broker details, queue/subscription definitions, interaction flags (`input_enabled`, etc.), and the processing logic reference?

3.  **Broker Interaction Flags (`input_enabled`, `output_enabled`, `request_reply_enabled`):**
    *   `input_enabled`: Does this imply the framework implicitly creates and manages a dedicated `BrokerInput` component instance for this app, listening on the specified queue?
    *   `output_enabled`: Does this imply a dedicated `BrokerOutput` instance? How does the app's processing logic trigger sending a message (e.g., returning a specific structure, calling a framework-provided function)?
    *   `request_reply_enabled`: Does this imply a dedicated `BrokerRequestResponse` instance? Is the simplified app acting as the *requester* or the *responder*? How does the app logic initiate a request or formulate a reply?

4.  **Shared vs. Dedicated Broker Components:**
    *   Based on our discussion, the preference seems to be for implicitly creating *dedicated* broker components (`BrokerInput`, `BrokerOutput`, `BrokerRequestResponse`) per simplified app instance rather than shared ones. Can we confirm this is the intended approach to maintain isolation and simplify acknowledgement/error handling?

5.  **Queue/Subscription Management:**
    *   Will the framework *always* attempt to create the specified queues and add subscriptions (`create_queue_on_start=True` behavior), or will this be configurable?
    *   What happens if the connector lacks the necessary SEMP permissions to create queues/subscriptions?
    *   How should conflicts be handled if two different simplified app definitions specify the same queue name?

6.  **Error Handling:**
    *   How are exceptions raised within the app's processing logic handled? Will they trigger a NACK back to the broker (if applicable)? Will they be sent to the main error queue?
    *   How are broker connection errors handled for the implicitly created components? Will reconnections be attempted based on the app's broker config?

7.  **Output Mechanism Details:**
    *   If `output_enabled` is true, what specific mechanism will the app's processing logic use to specify the payload, topic, and user properties of the message to be sent? (e.g., return a dict `{"payload": ..., "topic": ..., "user_properties": ...}`?)

8.  **Invocation Context:**
    *   When a message arrives (`input_enabled`), what context/data structure is passed to the app's processing logic? Is it the standard `Message` object?

9.  **Integration and Coexistence:**
    *   Can these simplified apps run within the same `SolaceAiConnector` instance alongside standard apps defined with explicit flows?

10. **Lifecycle and Scalability:**
    *   How are simplified apps started/stopped? Is it tied to the main connector lifecycle?
    *   Will there be a way to run multiple instances of the same simplified app definition (similar to `num_instances` for flows/components)? If so, how is naming/identification handled?

11. **"Invoke Method" per Subscription:**
    *   The description mentions "Each subscription can have an optional 'invoke method'". How does this relate to the main processing logic? Does this allow different functions/components to be called based on the specific subscription matched, overriding the main logic? If so, how is this configured?
</inst>
