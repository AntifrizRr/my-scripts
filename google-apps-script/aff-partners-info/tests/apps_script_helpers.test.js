const assert = require('assert');
const vm = require('vm');
const fs = require('fs');
const path = require('path');

const codePath = path.join(__dirname, '..', 'Code.gs');
const code = fs.readFileSync(codePath, 'utf8');

function loadCode() {
    const sandbox = {
        console,
        Logger: { log: () => { } },
        PropertiesService: { getScriptProperties: () => ({ getProperty: () => null }) },
        SpreadsheetApp: { getActive: () => null },
        UrlFetchApp: { fetch: () => ({ getResponseCode: () => 200, getContentText: () => 'ok' }) },
        Utilities: { sleep: () => { } },
        JSON,
        Number,
        String,
        Set,
        Map,
        Date,
        Math,
        RegExp,
        Array,
        Object,
        Boolean,
        parseInt,
        parseFloat,
        isNaN,
        Infinity,
        NaN,
    };

    const context = vm.createContext(sandbox);
    vm.runInContext(code, context, { filename: 'Code.gs' });
    return context;
}

const context = loadCode();

function run(name, fn) {
    try {
        fn();
        console.log(`PASS ${name}`);
    } catch (error) {
        console.error(`FAIL ${name}`);
        throw error;
    }
}

run('normalizeHeader_ trims and normalizes headers', () => {
    assert.strictEqual(context.normalizeHeader_('  Partner Name  '), 'partner name');
    assert.strictEqual(context.normalizeHeader_('Partner\tName'), 'partner name');
});

run('parseLocalizedNumber_ handles localized formats', () => {
    assert.strictEqual(context.parseLocalizedNumber_('1.234,56'), 1234.56);
    assert.strictEqual(context.parseLocalizedNumber_('1,234'), 1234);
    assert.strictEqual(context.parseLocalizedNumber_('1 234,50'), 1234.5);
    assert.strictEqual(context.parseLocalizedNumber_('not-a-number'), null);
});

run('parseDateValue_ handles valid dates', () => {
    assert.deepStrictEqual(context.parseDateValue_('2024-01-15'), new Date('2024-01-15T00:00:00.000Z'));
    assert.deepStrictEqual(context.parseDateValue_('15/01/2024'), new Date('2024-01-15T00:00:00.000Z'));
});

run('parseDateValue_ rejects invalid calendar date', () => {
    assert.strictEqual(context.parseDateValue_('2024-02-30'), null);
    assert.strictEqual(context.parseDateValue_('31/02/2024'), null);
});

run('hasDuplicateUniqueKey_ detects duplicates', () => {
    assert.strictEqual(context.hasDuplicateUniqueKey_(['A', 'B', 'A']), true);
    assert.strictEqual(context.hasDuplicateUniqueKey_(['A', 'B', 'C']), false);
});

run('rangesIntersect_ finds overlaps', () => {
    assert.strictEqual(context.rangesIntersect_([1, 3], [2, 4]), true);
    assert.strictEqual(context.rangesIntersect_([1, 2], [3, 4]), false);
});

run('escapeSlackText_ handles markdown and mentions', () => {
    assert.strictEqual(context.escapeSlackText_('Hello <@synthetic-user> *world*'), 'Hello &lt;@synthetic-user&gt; \*world\*');
    assert.strictEqual(context.escapeSlackText_('A&B'), 'A&amp;B');
});

run('normalizeEntityKey_ normalizes keys', () => {
    assert.strictEqual(context.normalizeEntityKey_('  Partner Name  '), 'partner_name');
    assert.strictEqual(context.normalizeEntityKey_('Partner\tName'), 'partner_name');
});
