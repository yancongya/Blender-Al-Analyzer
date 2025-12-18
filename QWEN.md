# QWEN.md - AI Node Analyzer Blender Add-on

## Project Overview

This project is a Blender addon named "AI Node Analyzer". Its primary function is to allow users to select nodes in Blender's various node editors (Geometry, Shader, Compositor, etc.) and get an analysis, explanation, or optimization suggestions from an AI model.

The addon is architecturally interesting as it's a hybrid system:
- **Core Addon (`__init__.py`):** A standard Blender addon written in Python using the `bpy` API. It creates a UI panel in the Node Editor, contains logic to parse Blender node graphs into a JSON format, and calls AI services (DeepSeek and Ollama are supported).
- **Backend Server (`backend/server.py`):** An optional, integrated Flask web server that runs in a background thread. This server exposes a REST API.
- **Frontend UI (`frontend/src/index.html`):** A simple, single-page web application served by the Flask backend. This UI acts as a remote control and communication interface, allowing a user to interact with the Blender addon from a web browser.

The main purpose of the backend/frontend components is to enable communication between the Blender addon and external applications, providing a powerful way to extend its functionality.

## Building and Running

This is a Blender addon and is not a standalone application. It needs to be run inside Blender.

### 1. Installation

1.  Open Blender.
2.  Go to `Edit > Preferences > Add-ons`.
3.  Click "Install..." and navigate to this project's directory.
4.  Select the `__init__.py` file and click "Install Add-on".
5.  Enable the "AI Node Analyzer" addon by checking the box next to it.
6.  The addon will attempt to install required Python packages (`Flask`, `Flask-CORS`) if they are not already present in Blender's Python environment.

### 2. Core AI Analysis Usage

1.  Open any node-based editor in Blender (e.g., Geometry Node Editor, Shader Editor).
2.  Press `N` to open the sidebar. A new tab named "AI Node Analyzer" will be visible.
3.  Select one or more nodes you wish to analyze.
4.  Configure the AI provider (DeepSeek or Ollama) and other settings via the `Preferences` (gear icon) button in the panel.
5.  Enter a question in the text box, or use the "Default" button.
6.  Click the **"Ask AI"** button.
7.  The addon will parse the selected nodes, send the data and your question to the configured AI service, and display the result in a new text block in Blender's Text Editor named `AINodeAnalysisResult`.

### 3. Backend Server and Web UI Usage

The addon includes an optional backend server for browser-based interaction.

1.  In the "AI Node Analyzer" panel, under the "Backend Server" section, click the **"Start"** button. This will launch the local Flask server.
2.  Once the server is running, click the **"Web"** button. This will open the frontend communication interface in your default web browser (`http://127.0.0.1:5000`).
3.  On the web page:
    *   Click **"Refresh Content"** to pull the currently selected node data from Blender into the "Send Content" box on the web page. This action is equivalent to pressing the "Refresh" button in the addon UI.
    *   Type a question into the text area.
    *   Click **"Send"** to send the node data and the question to the backend's streaming AI endpoint for analysis. The AI's response will be streamed into the "Received Content" box.

## Development Conventions

### Project Structure

-   `__init__.py`: The main entry point and core logic for the Blender addon. It handles UI panels, operators, node parsing, and direct communication with AI services.
-   `backend/server.py`: Contains the Flask application. It's launched in a background thread from the main addon. It defines all the API endpoints for external communication.
-   `frontend/src/index.html`: A vanilla JavaScript and HTML page that provides a user interface for interacting with the backend server's API.
-   `docs/`: Contains documentation, including the `COMMUNICATION_GUIDE.md` which details the backend architecture.

### Communication Protocol (Web UI <-> Backend)

The backend server provides a simple REST API. Key endpoints include:

-   `GET /api/test-connection`: Checks if the server is running.
-   `GET /api/blender-data`: Fetches the node graph data that has been prepared in Blender via the "Refresh" button.
-   `POST /api/stream-ai-response`: Sends a question and the node context to the backend to get a streamed response from a (simulated) AI service.

The communication flow is designed to be initiated from the user's action, either within Blender or from the web UI, ensuring the Blender UI remains responsive.

## Key Features

- **Node Parsing**: Recursive parsing of node trees, including nested node groups
- **Multi-AI Support**: Support for DeepSeek and Ollama AI providers
- **Browser Communication**: Integrated Flask server for external app communication
- **Web Interface**: Simple web UI for remote interaction with the addon
- **Text Output**: Analysis results saved to Blender's text editor