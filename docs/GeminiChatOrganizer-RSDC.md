# Gemini Chat Organizer RSDC Specification Document

This document defines the development framework for the "Gemini Chat Organizer," aimed at transforming raw AI conversations into structured, high-value knowledge assets.

## 1. Requirements — "What problems are we solving?"

### 1.1 Target Users

- Professional users who frequently interact with Gemini and need to transform conversation content into reports, notes, or development logs.  
- Users who wish to preserve and manage all AI history records locally.

### 1.2 Core Vision

- To eliminate noise from conversations, elevating AI dialogue from a "procedural tool" to a "knowledge asset," while providing full-process digital provenance.

### 1.3 Current Pain Points

- **Excessive Procedural Noise**: Conversations often contain multiple error-correction cycles and repetitive attempts ("procedural prompts"). Exporting them directly leads to blurred focus.  
- **Lack of Local Backup**: Cloud conversation search is inconvenient, and records cannot be edited or organized offline.  
- **Missing Metadata**: Exported text often lacks precise timestamps, making it difficult to reconstruct the context of thought.

### 1.4 System Goals

- **Full Download**: Support complete mirroring of cloud conversations to a local path.  
- **Precise Filtering**: Provide an interface for users to filter (hide/show) specific conversation blocks.  
- **Context Preservation**: Mandatory recording of the date and timestamp for every conversation turn.  
- **Standardized Output**: Final results must be convertible into industry-standard Markdown format.

## 2. Specification — "What are the rules of the system?"

### 2.1 Hierarchy

- **Archive**: The top-level data container storing all downloaded conversations.  
- **Session**: A single-topic conversation chain.  
- **Turn**: The smallest logical unit, consisting of one Prompt and one Response.

### 2.2 Artifact Types and Flow

- **Raw Source**: Original data obtained from Gemini API/Download (containing all history).  
- **Selection State**: Show/Hide markers for each Turn; these markers must be persistent.  
- **Final Artifact**: The Markdown document generated based on the selection states.

### 2.3 Naming and Data Structure

- **Timestamp Standard**: Uniformly use the YYYY-MM-DD HH:mm:ss format.  
- **State Attributes**: Each conversation Turn must possess a `visibility_flag` (boolean) and a timestamp attribute.

### 2.4 Config Schemas

- `sync_config.yaml`: Defines download frequency and storage paths.  
- `export_template.yaml`: Defines Markdown output templates (e.g., whether to show timestamps in headers, line break formats).

### 2.5 UI Interaction

- **Visibility Toggle**: Each Turn must expose a per-Turn control on the leading edge of its header that flips its `visibility_flag`. The state change must persist immediately (no separate save action).  
- **Hide-Hidden Filter**: The UI must provide a global toggle that, when active, removes Turns whose `visibility_flag` is `false` from the Turn view. While the filter is active, Sessions whose Turns are all hidden must also be removed from the Session list, and reappear automatically as soon as any of their Turns becomes visible again.  
- **Session Sort Order**: The Session list must be sortable by start time in either ascending or descending direction; sort direction is a view-only preference and must not alter persisted state.

## 3. Design — "How is the system architected?"

### 3.1 Core Component Responsibilities

- **Node.js Bridge**:  
  - Responsible for running the UI.  
  - Manages the lifecycle of the Python core process.  
  - Handles user click actions on the interface (Hide/Show operations).  
- **Python Processing Core**:  
  - **Downloader**: Interfaces with Gemini to perform data scraping.  
  - **Parser**: Parses raw data into the specified Turn objects.  
  - **Exporter**: Synthesizes Markdown files based on selection states and templates.  
- **Local Repository**: Stores raw and processed data files.

### 3.2 Directory Structure

```
ui/                  Node.js frontend code
engine/              Python core logic code
warehouse/
├── raw/             Downloaded raw JSON
└── processed/       Data with state markers
exports/             Final generated Markdown files
```

### 3.3 Execution Flow

1. User triggers "Sync"; Node.js calls Python Downloader to download data to warehouse/raw/.  
2. Python Parser processes data and returns it to Node.js UI for display.  
3. User toggles `visibility_flag` in the UI; the state is written to warehouse/processed/ in real-time.  
4. User executes "Organize"; Python Exporter reads the state and generates the .md file.

## 4. Coding — "How to write the code?"

### 4.1 Key Development Principles

- **IPC Driven**: Data is passed between Node.js and Python via Standard I/O (STDIN/STDOUT) or local Sockets using JSON; direct memory manipulation of the other process is strictly prohibited.  
- **Dynamic Path Injection**: All file paths must be passed as arguments by Node.js when launching Python; hardcoding relative paths in Python code is strictly prohibited.  
- **Strong Type Declaration**: The Python side must use the typing module to annotate function signatures.

### 4.2 Implementation Tools and Libraries

- **Node.js**: Use the `child_process` module to execute Python.  
- **Python**: Use pathlib for path handling, pydantic for data validation, and markdown-it or jinja2 for document generation.

### 4.3 Security and Robustness

- **Data Locking**: When Python Exporter is reading data, the Node.js interface should lock editing functions to prevent data races.  
- **Error Handling**: Any exceptions from the Python side must be encapsulated into a JSON error format and returned to the Node.js UI.

### 4.4 Task Generation

- Use automation scripts to ensure Python dependencies (requirements.txt) and Node dependencies remain synchronized in the development environment.
