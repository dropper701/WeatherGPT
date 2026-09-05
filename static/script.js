const userInput = document.getElementById("user-input");

const sendButton = document.getElementById("send-button");

const chatContainer = document.getElementById("chat-container");


// Function to send a message
async function sendMessage() {

    // Get the text typed by the user
    const message = userInput.value.trim();

    // Stop if the input is empty
    if (message === "") {
        return;
    }


    // Create the user's message
    const userMessage = document.createElement("div");

    userMessage.classList.add("message", "user-message");

    userMessage.innerHTML = `
        <div class="message-text">
            ${message}
        </div>
    `;

    // Add user message to chat
    chatContainer.appendChild(userMessage);


    // Clear input
    userInput.value = "";


    try {

        // Send message to FastAPI
        const response = await fetch("/chat", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                message: message
            })

        });


        // Get response from FastAPI
        const data = await response.json();

        console.log("Data received:", data);


        // Create bot message
        const botMessage = document.createElement("div");

        botMessage.classList.add("message", "bot-message");

        botMessage.innerHTML = `
            <div class="avatar">🌦️</div>

            <div class="message-text">
                ${data.reply}
            </div>
        `;


        // Add bot message to chat
        chatContainer.appendChild(botMessage);


        // Automatically scroll down
        chatContainer.scrollTop = chatContainer.scrollHeight;

    } catch (error) {

        console.error("Error:", error);

    }

}


// Send message when Send button is clicked
sendButton.addEventListener("click", sendMessage);


// Send message when Enter key is pressed
userInput.addEventListener("keydown", (event) => {

    if (event.key === "Enter") {
        sendMessage();
    }

});