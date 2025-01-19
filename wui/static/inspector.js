document.addEventListener("DOMContentLoaded", function() {
    fetchMemories();
});

function fetchMemories() {
    const url = "/api/memories";

    fetch(url)
        .then(response => response.json())
        .then(data => {
            displayMemories(data.memories);
            if (data.graph_file) {
                document.getElementById("current-graph-file").textContent = data.graph_file;
            }
        })
        .catch(error => {
            console.error("Error fetching memories:", error);
            const container = document.getElementById("memories-container");
            container.innerHTML = "<p>Error loading memories.</p>";
        });
}

function displayMemories(memories) {
    const container = document.getElementById("memories-container");
    container.innerHTML = "";

    if (memories.length === 0) {
        container.innerHTML = "<p>No memories found.</p>";
        return;
    }

    memories.forEach(mem => {
        const memoryDiv = document.createElement("div");
        memoryDiv.classList.add("memory");

        const header = document.createElement("div");
        header.classList.add("memory-header");
        const date = new Date(mem.timestamp * 1000).toLocaleString();
        const idTypeSpan = document.createElement("span");
        idTypeSpan.textContent = `ID: ${mem.memory_id} | Type: ${mem.memory_type}`;
        const timestampSpan = document.createElement("span");
        timestampSpan.textContent = date;
        header.appendChild(idTypeSpan);
        header.appendChild(timestampSpan);

        const content = document.createElement("div");
        content.classList.add("memory-content");
        content.textContent = mem.content;

        memoryDiv.appendChild(header);
        memoryDiv.appendChild(content);

        const footer = document.createElement("div");

        footer.classList.add("memory-footer");

        for (const [key, value] of Object.entries(mem.metadata)) {
            const metadataItem = document.createElement("span");
            metadataItem.classList.add("metadata-item");
            metadataItem.textContent = `${key}: ${typeof value === 'object' ? JSON.stringify(value) : value}`;
            footer.appendChild(metadataItem);
        }

        memoryDiv.appendChild(footer);

        container.appendChild(memoryDiv);
    });
}
