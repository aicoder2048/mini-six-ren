"""Electron-only settings panel. Existing credentials are never sent to the UI."""
from nicegui import ui

from ai_agent import SupportedModels
from utils.api_settings import APISettings, APISettingsError

PROVIDERS = (
    (SupportedModels.OPENAI_GPT61_SOL, 'OpenAI', 'https://platform.openai.com/api-keys'),
    (SupportedModels.DEEPSEEK_FLASH, 'DeepSeek', 'https://platform.deepseek.com/api_keys'),
)


class APISettingsPanel:
    def __init__(self, settings: APISettings, *, on_saved, is_running):
        self.settings = settings
        self.on_saved = on_saved
        self.is_running = is_running
        self.key_inputs = {}
        self.remove_checks = {}
        self.provider_status = {}
        self.official_links = {}
        with ui.dialog().props('persistent maximized aria-label="API Key 设置"') as self.dialog:
            with ui.card().classes('api-settings-page'):
                with ui.column().classes('api-settings-content'):
                    ui.label('AI 解读 · 连接设置').classes('eyebrow')
                    ui.label('设置 API Key').classes('serif api-settings-title').props('role=heading aria-level=1')
                    ui.label('连接一家即可获得三传解读；也可以稍后设置，先体验本地占卜。').classes('helper-text')
                    for model, name, url in PROVIDERS:
                        with ui.column().classes('api-provider-card').props(f'data-provider={name.lower()}'):
                            with ui.row().classes('section-heading'):
                                ui.label(name).classes('serif text-xl')
                                self.provider_status[model] = ui.label('').classes('api-provider-status')
                            self.official_links[model] = ui.link(f'打开 {name} 官方密钥管理页 ↗', url, new_tab=True).classes('api-official-link').props('rel=noopener')
                            self.key_inputs[model] = ui.input(
                                f'{name} API Key', password=True, password_toggle_button=True,
                                placeholder='已设置时留空可保留；输入新 Key 可替换',
                            ).classes('w-full').props('outlined hide-bottom-space autocomplete=new-password autocapitalize=off spellcheck=false')
                            for icon in self.key_inputs[model].slots['append'].children:
                                icon.props('role=button tabindex=0 aria-label="显示或隐藏新输入的密钥"')
                                icon.on('keydown.enter', js_handler='event => event.target.click()')
                                icon.on('keydown.space', js_handler='event => { event.preventDefault(); event.target.click(); }')
                            self.remove_checks[model] = ui.checkbox('删除此 Key').classes('api-remove-key')
                    ui.label('默认选择：两家都有 Key 时优先 OpenAI；只有一家则选该家。').classes('helper-text')
                    ui.label('Key 仅保存在本机配置文件中（非加密存储），不要分享此文件。保存不验证余额、权限或模型可用性，也不会自动调用 API。').classes('helper-text')
                    self.error = ui.label('').classes('error-message api-settings-error').props('role=alert')
                    with ui.row().classes('api-settings-actions'):
                        ui.button('稍后设置 / 返回占卜', on_click=self.skip).classes('api-settings-skip').props('flat no-caps')
                        ui.button('保存并返回', icon='check', on_click=self.save).classes('api-settings-save').props('unelevated no-caps')
        self.dialog.on('hide', self.clear_inputs)

    def clear_inputs(self):
        for field in self.key_inputs.values():
            field.set_value('')
            field.props('type=password')
            for icon in field.slots['append'].children:
                icon.props('name=visibility_off')
        for checkbox in self.remove_checks.values():
            checkbox.set_value(False)
        self.error.set_text('')

    def open(self):
        if self.is_running():
            ui.notify('正在解读，请等待完成后再修改 API 设置。', type='info')
            return
        self.clear_inputs()
        for model, _, _ in PROVIDERS:
            configured = bool(self.settings.key_for(model))
            self.provider_status[model].set_text('已配置（未验证）' if configured else '未配置')
            self.remove_checks[model].set_enabled(configured)
        self.dialog.open()

    def skip(self):
        self.clear_inputs()
        self.settings.dismiss_onboarding()
        self.dialog.close()

    def save(self):
        if self.is_running():
            self.error.set_text('正在解读，请等待完成后再保存。')
            return
        changes = {}
        for model, _, _ in PROVIDERS:
            value = self.key_inputs[model].value or ''
            remove = self.remove_checks[model].value
            if remove and value.strip():
                self.error.set_text('请在替换与删除之间选择一种操作。')
                return
            changes[model] = '' if remove else (value if value.strip() else None)
        if not self.settings.available_models and all(value is None for value in changes.values()):
            self.error.set_text('请填写至少一个 API Key，或点“稍后设置 / 返回占卜”。')
            return
        try:
            self.settings.save(changes)
        except APISettingsError as exc:
            self.error.set_text(str(exc))
            return
        self.clear_inputs()
        self.settings.dismiss_onboarding()
        self.on_saved()
        self.dialog.close()
        ui.notify('API 设置已保存并生效。', type='positive')
