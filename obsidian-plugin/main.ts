import { App, Modal, Notice, Plugin, PluginSettingTab, Setting } from 'obsidian';
import { exec } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

interface BlogPostCreatorSettings {
    scriptsPath: string;
    pythonPath: string;
    // WordPress
    wpUrl: string;
    wpUser: string;
    wpAppPassword: string;
    // LinkedIn
    linkedinAccessToken: string;
    linkedinPersonId: string;
    // Twitter / X
    twitterApiKey: string;
    twitterApiSecret: string;
    twitterAccessToken: string;
    twitterAccessTokenSecret: string;
    // OpenAI
    openaiApiKey: string;
}

const DEFAULT_SETTINGS: BlogPostCreatorSettings = {
    scriptsPath: '',
    pythonPath: 'python3',
    wpUrl: '',
    wpUser: '',
    wpAppPassword: '',
    linkedinAccessToken: '',
    linkedinPersonId: '',
    twitterApiKey: '',
    twitterApiSecret: '',
    twitterAccessToken: '',
    twitterAccessTokenSecret: '',
    openaiApiKey: '',
};

// Which config files each script needs written before it runs
const SCRIPT_CONFIGS: Record<string, string[]> = {
    'generate-image.py':  ['openai_config.py'],
    'publish.sh':         [],
    'wp-draft.py':        ['wp_config.py'],
    'linkedin-post.py':   ['linkedin_config.py'],
    'twitter-post.py':    ['twitter_config.py'],
    'sync-post-dates.py': ['wp_config.py'],
};

// ---------------------------------------------------------------------------
// Output modal
// ---------------------------------------------------------------------------

class OutputModal extends Modal {
    private title: string;
    private output: string;

    constructor(app: App, title: string, output: string) {
        super(app);
        this.title = title;
        this.output = output;
    }

    onOpen() {
        const { contentEl } = this;
        contentEl.createEl('h2', { text: this.title });
        const pre = contentEl.createEl('pre');
        pre.style.cssText = 'white-space: pre-wrap; font-family: monospace; font-size: 12px; max-height: 400px; overflow-y: auto;';
        pre.setText(this.output || '(no output)');
    }

    onClose() {
        this.contentEl.empty();
    }
}

// ---------------------------------------------------------------------------
// Plugin
// ---------------------------------------------------------------------------

export default class BlogPostCreator extends Plugin {
    settings: BlogPostCreatorSettings;

    async onload() {
        await this.loadSettings();

        this.addCommand({
            id: 'generate-image',
            name: 'Generate header image',
            callback: () => this.runOnCurrentFile('generate-image.py', 'python'),
        });

        this.addCommand({
            id: 'convert-to-html',
            name: 'Convert to HTML',
            callback: () => this.runOnCurrentFile('publish.sh', 'bash'),
        });

        this.addCommand({
            id: 'push-to-wordpress',
            name: 'Push to WordPress as draft',
            callback: () => this.runOnCurrentFile('wp-draft.py', 'python'),
        });

        this.addCommand({
            id: 'post-to-linkedin',
            name: 'Post to LinkedIn',
            callback: () => this.runOnCurrentFile('linkedin-post.py', 'python'),
        });

        this.addCommand({
            id: 'post-to-twitter',
            name: 'Post to Twitter/X',
            callback: () => this.runOnCurrentFile('twitter-post.py', 'python'),
        });

        this.addCommand({
            id: 'sync-post-dates',
            name: 'Sync post dates from WordPress',
            callback: () => this.runScript('sync-post-dates.py', 'python', null),
        });

        this.addSettingTab(new BlogPostCreatorSettingTab(this.app, this));
    }

    async loadSettings() {
        this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
    }

    async saveSettings() {
        await this.saveData(this.settings);
    }

    // -----------------------------------------------------------------------
    // Config file helpers
    // -----------------------------------------------------------------------

    private buildConfigContent(configName: string): string {
        const s = this.settings;
        switch (configName) {
            case 'wp_config.py':
                return [
                    `WP_URL = "${s.wpUrl}"`,
                    `WP_USER = "${s.wpUser}"`,
                    `WP_APP_PASSWORD = "${s.wpAppPassword}"`,
                ].join('\n') + '\n';

            case 'linkedin_config.py':
                return [
                    `LINKEDIN_ACCESS_TOKEN = "${s.linkedinAccessToken}"`,
                    `LINKEDIN_PERSON_ID = "${s.linkedinPersonId}"`,
                ].join('\n') + '\n';

            case 'twitter_config.py':
                return [
                    `TWITTER_API_KEY = "${s.twitterApiKey}"`,
                    `TWITTER_API_SECRET = "${s.twitterApiSecret}"`,
                    `TWITTER_ACCESS_TOKEN = "${s.twitterAccessToken}"`,
                    `TWITTER_ACCESS_TOKEN_SECRET = "${s.twitterAccessTokenSecret}"`,
                ].join('\n') + '\n';

            case 'openai_config.py':
                return `OPENAI_API_KEY = "${s.openaiApiKey}"\n`;

            default:
                return '';
        }
    }

    private writeConfigs(scriptName: string): string[] {
        const needed = SCRIPT_CONFIGS[scriptName] ?? [];
        const written: string[] = [];
        for (const configName of needed) {
            const configPath = path.join(this.settings.scriptsPath, configName);
            fs.writeFileSync(configPath, this.buildConfigContent(configName), { encoding: 'utf8', mode: 0o600 });
            written.push(configPath);
        }
        return written;
    }

    private deleteConfigs(paths: string[]) {
        for (const p of paths) {
            try { fs.unlinkSync(p); } catch { /* best effort */ }
        }
    }

    // -----------------------------------------------------------------------
    // Script execution
    // -----------------------------------------------------------------------

    private getCurrentFilePath(): string | null {
        const file = this.app.workspace.getActiveFile();
        if (!file || file.extension !== 'md') {
            new Notice('No markdown file is currently open.');
            return null;
        }
        const basePath = (this.app.vault.adapter as any).basePath as string;
        return path.join(basePath, file.path);
    }

    private runOnCurrentFile(scriptName: string, type: 'python' | 'bash') {
        const filePath = this.getCurrentFilePath();
        if (!filePath) return;
        this.runScript(scriptName, type, filePath);
    }

    private runScript(scriptName: string, type: 'python' | 'bash', filePath: string | null) {
        if (!this.settings.scriptsPath) {
            new Notice('Scripts path not set. Go to Settings → Blog Post Creator.');
            return;
        }

        const scriptPath = path.join(this.settings.scriptsPath, scriptName);
        const python = this.settings.pythonPath || 'python3';

        let cmd: string;
        if (type === 'python') {
            cmd = filePath
                ? `"${python}" "${scriptPath}" "${filePath}"`
                : `"${python}" "${scriptPath}"`;
        } else {
            cmd = filePath
                ? `bash "${scriptPath}" "${filePath}"`
                : `bash "${scriptPath}"`;
        }

        const label = scriptName.replace(/\.(py|sh)$/, '');
        new Notice(`Running ${label}…`);

        const writtenConfigs = this.writeConfigs(scriptName);

        exec(cmd, { cwd: this.settings.scriptsPath }, (error, stdout, stderr) => {
            this.deleteConfigs(writtenConfigs);
            const output = [stdout, stderr].filter(Boolean).join('\n').trim();
            const modalTitle = error ? `${label} — error` : `${label} — done`;
            new OutputModal(this.app, modalTitle, output || error?.message || '').open();
        });
    }
}

// ---------------------------------------------------------------------------
// Settings tab
// ---------------------------------------------------------------------------

class BlogPostCreatorSettingTab extends PluginSettingTab {
    plugin: BlogPostCreator;

    constructor(app: App, plugin: BlogPostCreator) {
        super(app, plugin);
        this.plugin = plugin;
    }

    display(): void {
        const { containerEl } = this;
        containerEl.empty();

        // ---- General -------------------------------------------------------
        containerEl.createEl('h2', { text: 'General' });

        new Setting(containerEl)
            .setName('Scripts folder path')
            .setDesc('Absolute path to the folder containing the blog post scripts.')
            .addText(text => text
                .setPlaceholder('/absolute/path/to/scripts')
                .setValue(this.plugin.settings.scriptsPath)
                .onChange(async (value) => {
                    this.plugin.settings.scriptsPath = value.trim();
                    await this.plugin.saveSettings();
                }));

        new Setting(containerEl)
            .setName('Python executable')
            .setDesc('Path to python3. Change if python3 is not on your PATH (e.g. /usr/local/bin/python3).')
            .addText(text => text
                .setPlaceholder('python3')
                .setValue(this.plugin.settings.pythonPath)
                .onChange(async (value) => {
                    this.plugin.settings.pythonPath = value.trim() || 'python3';
                    await this.plugin.saveSettings();
                }));

        // ---- WordPress -----------------------------------------------------
        containerEl.createEl('h2', { text: 'WordPress' });

        new Setting(containerEl)
            .setName('Site URL')
            .setDesc('e.g. https://yoursite.com')
            .addText(text => text
                .setPlaceholder('https://yoursite.com')
                .setValue(this.plugin.settings.wpUrl)
                .onChange(async (value) => {
                    this.plugin.settings.wpUrl = value.trim();
                    await this.plugin.saveSettings();
                }));

        new Setting(containerEl)
            .setName('Username')
            .addText(text => text
                .setPlaceholder('your_username')
                .setValue(this.plugin.settings.wpUser)
                .onChange(async (value) => {
                    this.plugin.settings.wpUser = value.trim();
                    await this.plugin.saveSettings();
                }));

        new Setting(containerEl)
            .setName('Application password')
            .setDesc('WordPress Admin → Users → Your Profile → Application Passwords.')
            .addText(text => {
                text.setPlaceholder('xxxx xxxx xxxx xxxx xxxx xxxx')
                    .setValue(this.plugin.settings.wpAppPassword)
                    .onChange(async (value) => {
                        this.plugin.settings.wpAppPassword = value;
                        await this.plugin.saveSettings();
                    });
                text.inputEl.type = 'password';
            });

        // ---- LinkedIn ------------------------------------------------------
        containerEl.createEl('h2', { text: 'LinkedIn' });

        new Setting(containerEl)
            .setName('Access token')
            .setDesc('Expires after 60 days. Regenerate at linkedin.com/developers/tools/oauth/token-generator.')
            .addText(text => {
                text.setPlaceholder('your_access_token')
                    .setValue(this.plugin.settings.linkedinAccessToken)
                    .onChange(async (value) => {
                        this.plugin.settings.linkedinAccessToken = value.trim();
                        await this.plugin.saveSettings();
                    });
                text.inputEl.type = 'password';
            });

        new Setting(containerEl)
            .setName('Person ID')
            .setDesc('Shown on the OAuth token generator page after generating a token.')
            .addText(text => text
                .setPlaceholder('AbCd12EfGh')
                .setValue(this.plugin.settings.linkedinPersonId)
                .onChange(async (value) => {
                    this.plugin.settings.linkedinPersonId = value.trim();
                    await this.plugin.saveSettings();
                }));

        // ---- Twitter / X ---------------------------------------------------
        containerEl.createEl('h2', { text: 'Twitter / X' });

        new Setting(containerEl)
            .setName('API key')
            .addText(text => {
                text.setPlaceholder('your_api_key')
                    .setValue(this.plugin.settings.twitterApiKey)
                    .onChange(async (value) => {
                        this.plugin.settings.twitterApiKey = value.trim();
                        await this.plugin.saveSettings();
                    });
                text.inputEl.type = 'password';
            });

        new Setting(containerEl)
            .setName('API secret')
            .addText(text => {
                text.setPlaceholder('your_api_secret')
                    .setValue(this.plugin.settings.twitterApiSecret)
                    .onChange(async (value) => {
                        this.plugin.settings.twitterApiSecret = value.trim();
                        await this.plugin.saveSettings();
                    });
                text.inputEl.type = 'password';
            });

        new Setting(containerEl)
            .setName('Access token')
            .addText(text => {
                text.setPlaceholder('your_access_token')
                    .setValue(this.plugin.settings.twitterAccessToken)
                    .onChange(async (value) => {
                        this.plugin.settings.twitterAccessToken = value.trim();
                        await this.plugin.saveSettings();
                    });
                text.inputEl.type = 'password';
            });

        new Setting(containerEl)
            .setName('Access token secret')
            .addText(text => {
                text.setPlaceholder('your_access_token_secret')
                    .setValue(this.plugin.settings.twitterAccessTokenSecret)
                    .onChange(async (value) => {
                        this.plugin.settings.twitterAccessTokenSecret = value.trim();
                        await this.plugin.saveSettings();
                    });
                text.inputEl.type = 'password';
            });

        // ---- OpenAI --------------------------------------------------------
        containerEl.createEl('h2', { text: 'OpenAI' });

        new Setting(containerEl)
            .setName('API key')
            .setDesc('platform.openai.com/api-keys')
            .addText(text => {
                text.setPlaceholder('sk-proj-...')
                    .setValue(this.plugin.settings.openaiApiKey)
                    .onChange(async (value) => {
                        this.plugin.settings.openaiApiKey = value.trim();
                        await this.plugin.saveSettings();
                    });
                text.inputEl.type = 'password';
            });
    }
}
