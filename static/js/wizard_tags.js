document.addEventListener('DOMContentLoaded', function() {
    const tagsHidden = document.getElementById('tags-hidden');
    const tagsWrap = document.getElementById('tags-wrap');
    const tagInput = document.getElementById('tag-input');

    if (!tagInput || !tagsWrap || !tagsHidden) return;

    tagInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            const value = tagInput.value.trim();
            if (value) {
                addTag(value);
                tagInput.value = '';
            }
        }
    });

    function addTag(name) {
        const span = document.createElement('span');
        span.className = 'tag';
        span.innerHTML = `${name} <span class="tag-remove" onclick="removeTag(this)">×</span>`;
        tagsWrap.insertBefore(span, tagInput);
        updateTagsHidden();
    }

    window.removeTag = function(el) {
        el.parentElement.remove();
        updateTagsHidden();
    }

    function updateTagsHidden() {
        const tags = [...tagsWrap.querySelectorAll('.tag')]
            .map(t => t.childNodes[0].textContent.trim());
        tagsHidden.value = tags.join(',');
    }

    updateTagsHidden();

    // Debug — remove after testing
    document.querySelector('form').addEventListener('submit', function() {
        console.log('Tags being submitted:', tagsHidden.value);
    });
});