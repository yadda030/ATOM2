// Tag management
const tagsHidden = document.getElementById('tags-hidden');
const tagsWrap = document.getElementById('tags-wrap');
const tagInput = document.getElementById('tag-input');

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

function removeTag(el) {
    el.parentElement.remove();
    updateTagsHidden();
}

function updateTagsHidden() {
    const tags = [...tagsWrap.querySelectorAll('.tag')]
        .map(t => t.childNodes[0].textContent.trim());
    tagsHidden.value = tags.join(',');
}

// Variable management
let varCount = document.querySelectorAll('.variable-row').length;
const totalForms = document.getElementById('id_variables-TOTAL_FORMS');

function addVariable() {
    const tbody = document.getElementById('variables-tbody');
    const row = document.createElement('tr');
    row.className = 'variable-row';
    row.innerHTML = `
        <td>
            <input class="variable-input" type="text" name="variables-${varCount}-key" placeholder="variable_name" />
            <input type="hidden" name="variables-${varCount}-DELETE" class="delete-field" value="" />
        </td>
        <td>
            <select class="variable-input" name="variables-${varCount}-variable_type">
                <option value="string">String</option>
                <option value="integer">Integer</option>
                <option value="boolean">Boolean</option>
                <option value="ip_address">IP Address</option>
            </select>
        </td>
        <td><input class="variable-input" type="text" name="variables-${varCount}-default_value" placeholder="Optional default" /></td>
        <td><input class="variable-input" type="text" name="variables-${varCount}-description" placeholder="What is this variable?" /></td>
        <td>
            <select class="variable-input" name="variables-${varCount}-required">
                <option value="True">Required</option>
                <option value="False">Optional</option>
            </select>
        </td>
        <td><button type="button" class="btn-remove" onclick="removeVariable(this)">×</button></td>
    `;
    tbody.appendChild(row);
    varCount++;
    totalForms.value = varCount;
}

function removeVariable(btn) {
    const row = btn.closest('tr');
    const deleteField = row.querySelector('.delete-field');
    if (deleteField) {
        deleteField.value = 'on';
        row.style.display = 'none';
    } else {
        row.remove();
    }
}

function toggleGuide() {
    const guidePanel = document.getElementById('guide-panel');
    const editorRow = document.getElementById('editor-row');
    const toggle = document.getElementById('guide-toggle');
    const guideTitle = document.getElementById('guide-title');

    if (guidePanel.classList.contains('collapsed')) {
        guidePanel.classList.remove('collapsed');
        editorRow.style.gridTemplateColumns = '1fr 260px';
        toggle.textContent = '▶';
        guideTitle.style.display = 'block';
    } else {
        guidePanel.classList.add('collapsed');
        editorRow.style.gridTemplateColumns = '1fr 36px';
        toggle.textContent = '◀';
        guideTitle.style.display = 'none';
    }
}