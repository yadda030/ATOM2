document.addEventListener('DOMContentLoaded', function() {
    const tagsHidden = document.getElementById('tags-hidden');
    const tagsWrap = document.getElementById('tags-wrap');
    const tagInput = document.getElementById('tag-input');

    if (!tagInput) return;

    tagInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            const value = tagInput.value.trim();
            if (value) {
                addTag(value);
                tagInput.value = '';
                updateTagsHidden();
            }
        }
    });

    function addTag(name) {
        const span = document.createElement('span');
        span.className = 'tag';
        span.innerHTML = `${name} <span class="tag-remove" onclick="removeTag(this)">×</span>`;
        tagsWrap.insertBefore(span, tagInput);
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
});