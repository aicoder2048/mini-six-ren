"""Desktop-only API settings; never place persisted secrets in browser state."""
from contextlib import suppress
import os
from pathlib import Path
import tempfile
from threading import RLock
from typing import Mapping

from dotenv import dotenv_values, set_key

from ai_agent import SupportedModels

DESKTOP_MODEL_PRIORITY = (SupportedModels.OPENAI_GPT61_SOL, SupportedModels.DEEPSEEK_FLASH)


class APISettingsError(ValueError):
    """Safe user-facing error: contains no credential or underlying OS details."""


class APISettings:
    def __init__(self, path: Path, *, environ: Mapping[str, str] | None = None):
        self.path = Path(path)
        inherited = os.environ if environ is None else environ
        try:
            values = dotenv_values(self.path, interpolate=False, encoding='utf-8') if self.path.exists() else {}
        except (OSError, UnicodeError):
            raise APISettingsError('无法读取本机 API 配置，请检查配置文件的权限与编码。') from None
        self._keys = {}
        for model in DESKTOP_MODEL_PRIORITY:
            name = SupportedModels.get_api_key_name(model)
            # An explicit empty file value masks inherited credentials, including after restart.
            value = values[name] if name in values else inherited.get(name, '')
            self._keys[model] = (value or '').strip()
        self._onboarding_dismissed = False
        self._lock = RLock()

    @property
    def available_models(self):
        return [model for model in DESKTOP_MODEL_PRIORITY if self._keys[model]]

    @property
    def default_model(self):
        return next(iter(self.available_models), None)

    @property
    def needs_onboarding(self):
        return not self.available_models and not self._onboarding_dismissed

    def dismiss_onboarding(self):
        self._onboarding_dismissed = True

    def key_for(self, model: SupportedModels) -> str:
        return self._keys[model]

    def save(self, changes: Mapping[SupportedModels, str | None]):
        """None keeps a key, empty string deletes it; validate everything before writing."""
        normalized = {}
        for model, value in changes.items():
            if model not in DESKTOP_MODEL_PRIORITY:
                raise APISettingsError('不支持的 API 供应商。')
            if value is None:
                continue
            if not isinstance(value, str):
                raise APISettingsError('请输入有效的 API Key。')
            value = value.strip()
            if len(value) > 512 or any(not 33 <= ord(char) <= 126 or char == '\\' for char in value):
                raise APISettingsError('API Key 不能包含内部空白、中文、反斜杠或控制字符，且不能超过 512 个字符。')
            normalized[model] = value
        if not normalized:
            return
        with self._lock:
            temporary = None
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                if self.path.is_symlink():
                    raise OSError('symlink settings file is not supported')
                original = self.path.read_text(encoding='utf-8') if self.path.exists() else ''
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent,
                                                 prefix='.api-settings-', delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(original)
                for model, value in normalized.items():
                    set_key(temporary, SupportedModels.get_api_key_name(model), value, quote_mode='always')
                # Verify with the same parser used on startup before replacing any saved file.
                persisted = dotenv_values(temporary, interpolate=False, encoding='utf-8')
                if any(persisted.get(SupportedModels.get_api_key_name(model)) != value
                       for model, value in normalized.items()):
                    raise APISettingsError('配置写入校验失败，原配置未更改。请检查 Key 格式后重试。')
                if os.name != 'nt':
                    temporary.chmod(0o600)
                os.replace(temporary, self.path)
                self._keys.update(normalized)
            except (OSError, UnicodeError):
                raise APISettingsError('保存失败，原配置未更改。请检查配置目录权限或磁盘空间后重试。') from None
            finally:
                if temporary is not None:
                    with suppress(OSError):
                        temporary.unlink(missing_ok=True)
