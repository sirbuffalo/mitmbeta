(function () {
    const tree = document.getElementById('video-tree');
    const lines = document.getElementById('video-tree-lines');

    function drawLines() {
        if (!tree || !lines) {
            return;
        }

        const treeBounds = tree.getBoundingClientRect();
        lines.setAttribute('viewBox', `0 0 ${treeBounds.width} ${treeBounds.height}`);
        lines.setAttribute('width', String(treeBounds.width));
        lines.setAttribute('height', String(treeBounds.height));
        lines.replaceChildren();

        const nodes = new Map(
            [...tree.querySelectorAll('.video-node[data-video-id]')]
                .map((node) => [node.dataset.videoId, node])
        );

        nodes.forEach((node) => {
            const dependencyIds = (node.dataset.dependencies || '')
                .split(',')
                .filter(Boolean);

            const nodeBounds = node.getBoundingClientRect();
            const startX = nodeBounds.left + (nodeBounds.width / 2) - treeBounds.left;
            const startY = nodeBounds.bottom - treeBounds.top;

            dependencyIds.forEach((dependencyId) => {
                const dependencyNode = nodes.get(dependencyId);
                if (!dependencyNode) return;

                const dependencyBounds = dependencyNode.getBoundingClientRect();
                const endX = dependencyBounds.left + (dependencyBounds.width / 2) - treeBounds.left;
                const endY = dependencyBounds.top - treeBounds.top;
                const middleY = startY + ((endY - startY) / 2);

                const line = document.createElementNS(
                    'http://www.w3.org/2000/svg',
                    'path'
                );

                line.setAttribute(
                    'd',
                    `M ${startX} ${startY} C ${startX} ${middleY}, ${endX} ${middleY}, ${endX} ${endY}`
                );

                line.setAttribute('class', 'video-tree-line');
                lines.append(line);
            });
        });
    }

    function syncFinishedHighlight(checkbox) {
        const node = checkbox.closest('.video-node');
        if (node) {
            node.classList.toggle('is-finished', checkbox.checked);
        }
    }

    document
        .querySelectorAll('.video-node-finished input[type="checkbox"]')
        .forEach(syncFinishedHighlight);

    document.addEventListener('change', (event) => {
        if (!(event.target instanceof HTMLInputElement) ||
            event.target.type !== 'checkbox') {
            return;
        }

        const node = event.target.closest('.video-node');
        if (!node) {
            return;
        }

        syncFinishedHighlight(event.target);

        if (!node.dataset.progressUrl) {
            return;
        }

        const requestedChecked = event.target.checked;

        fetch(node.dataset.progressUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                seconds: requestedChecked ? 1 : 0,
                duration: requestedChecked ? 1 : null,
                finished: requestedChecked,
            }),
        })
        .then((response) => {
            if (!response.ok) {
                throw new Error('Progress was not saved.');
            }
            return response.json();
        })
        .then((data) => {
            event.target.checked = Boolean(data.finished);
            syncFinishedHighlight(event.target);
        })
        .catch((error) => {
            console.error(error);
            event.target.checked = !requestedChecked;
            syncFinishedHighlight(event.target);
        });
    });

    if (tree && lines) {
        window.addEventListener('resize', drawLines);
        window.addEventListener('load', drawLines);
        requestAnimationFrame(drawLines);
    }
})();