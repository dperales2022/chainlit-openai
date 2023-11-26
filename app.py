#comment by Dani
import os

from openai import AsyncOpenAI
import chainlit as cl

api_key = os.environ.get("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=api_key)
assistant_id = os.environ.get("ASSISTANT_ID")


@cl.on_chat_start
async def start_chat():
    thread = await client.beta.threads.create()
    cl.user_session.set("thread", thread)
    await cl.Message(author="assistant", content="Ask me any questions!").send()


@cl.on_message
async def run_conversation(message_from_ui: cl.Message):
    thread = cl.user_session.get("thread")
    # Add the message to the thread
    oai_message = await client.beta.threads.messages.create(
        thread_id=thread.id, role="user", content=message_from_ui.content
    )

    # Create the run
    run = await client.beta.threads.runs.create(
        thread_id=thread.id, assistant_id=assistant_id
    )

    # Send empty message to display the loader
    response_msg = cl.Message(author="assistant", content="")
    await response_msg.send()

    running = True

    # Wait for the run to be completed
    while running:
        run = await client.beta.threads.runs.retrieve(
            thread_id=thread.id, run_id=run.id
        )
        if run.status in ["cancelled", "failed", "completed", "expired"]:
            break
        await cl.sleep(0.2)

    # Fetch the run steps
    run_steps = await client.beta.threads.runs.steps.list(
        thread_id=thread.id, run_id=run.id, order="asc"
    )

    for step in run_steps.data:
        # Fetch step details
        run_step = await client.beta.threads.runs.steps.retrieve(
            thread_id=thread.id, run_id=run.id, step_id=step.id
        )
        step_details = run_step.step_details
        # Send step content to the Chainlit UI
        if step_details.type == "message_creation":
            message = await client.beta.threads.messages.retrieve(
                message_id=step_details.message_creation.message_id,
                thread_id=thread.id,
            )
            response_msg.content = message.content[0].text.value
            await response_msg.update()
        if step_details.type == "tool_calls":
            for tool_call in step_details.tool_calls:
                if tool_call.type == "code_interpreter":
                    await cl.Message(
                        author=tool_call.type,
                        content=tool_call.code_interpreter.input,
                        language="python",
                        parent_id=message_from_ui.id,
                    ).send()
                    await cl.Message(
                        author=f"{tool_call.type}_result",
                        content=tool_call.code_interpreter.outputs,
                        parent_id=message_from_ui.id,
                    ).send()
                elif tool_call.type == "retrieval":
                    await cl.Message(
                        author=tool_call.type,
                        content="Retrieving information",
                        parent_id=message_from_ui.id,
                    ).send()
