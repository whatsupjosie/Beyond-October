"""Human profile fields and explicit disclosure; AI cartridges remain separate."""
from __future__ import annotations

import json
import io
import warnings
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TEXT_FIELDS = {
    'real_name':80, 'nickname':80, 'pronouns':80, 'city':120,
    'bio':4000, 'education':2000, 'skills':2000, 'resume':4000,
    'hobbies':2000, 'favorite_books':2000, 'favorite_movies':2000,
    'favorite_podcasts':2000, 'internet_recommendations':2000,
    'current_projects':2000, 'dream_project':2000, 'collaborations':2000,
}
LINK_FIELDS = {'website', 'portfolio', 'linkedin', 'reel'}
SHARE_FIELDS = set(TEXT_FIELDS) | LINK_FIELDS | {'experience', 'photo'}


def clean_link(value: str) -> str:
    value = value.strip()
    if not value:
        return ''
    if len(value) > 2048 or any(ord(c) < 32 or c.isspace() for c in value):
        raise ValueError('Links must be complete HTTP or HTTPS addresses without spaces')
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in {'https', 'http'} or not parsed.hostname or
                parsed.username is not None or parsed.password is not None):
            raise ValueError()
        parsed.port  # Reject malformed ports, too.
    except ValueError:
        raise ValueError('Links must be complete HTTP or HTTPS addresses') from None
    return value


class HumanProfileDetails(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    discoverable: bool = False
    public_fields: list[str] = Field(default_factory=list, max_length=32)
    about: dict[str, str] = Field(default_factory=dict)
    onboarding_complete: bool = False

    @field_validator('public_fields')
    @classmethod
    def valid_public_fields(cls, value):
        if len(value) != len(set(value)) or set(value) - SHARE_FIELDS:
            raise ValueError('Choose known, distinct profile fields to share')
        return value

    @field_validator('about')
    @classmethod
    def valid_about(cls, value):
        unknown = set(value) - (set(TEXT_FIELDS) | LINK_FIELDS | {'experience'})
        if unknown:
            raise ValueError('Unknown profile field')
        out = {}
        for key, text in value.items():
            if any(ord(c) < 32 and c not in '\n\t\r' for c in text):
                raise ValueError('Profile text contains control characters')
            if key in LINK_FIELDS:
                out[key] = clean_link(text)
            elif key == 'experience':
                if text not in {'', 'professional', 'hobbyist', 'learner'}:
                    raise ValueError('Choose professional, hobbyist or learner')
                out[key] = text
            else:
                if len(text) > TEXT_FIELDS[key]:
                    raise ValueError(f'{key} is too long')
                out[key] = text
        return out

    @model_validator(mode='after')
    def bounded_profile(self):
        if len(json.dumps(self.model_dump(), ensure_ascii=False).encode()) > 24000:
            raise ValueError('Keep the complete profile under 24 KB')
        return self


def details(value=None) -> dict:
    """Empty historical profiles migrate privately, never into discovery."""
    return HumanProfileDetails.model_validate(value or {}).model_dump()


def shared_about(profile: dict, fields: list[str] | None = None) -> dict:
    data = details(profile.get('details'))
    selected = set(data['public_fields'] if fields is None else fields)
    if selected - SHARE_FIELDS:
        raise ValueError('Unknown sharing field')
    return {k:v for k,v in data['about'].items() if k in selected and v}


def normalize_photo(data: bytes) -> bytes:
    """Bound decode size and remove metadata before a profile image is served."""
    from PIL import Image, ImageOps
    if not data or len(data) > 2 * 1024 * 1024:
        raise ValueError('Choose a PNG, JPEG or WebP image under 2 MB')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if (image.format not in {'PNG','JPEG','WEBP'} or getattr(image,'n_frames',1) != 1
                        or not 1 <= image.width <= 2048 or not 1 <= image.height <= 2048):
                    raise ValueError('Choose a still image no larger than 2048 by 2048')
                image.load()
                prepared = ImageOps.exif_transpose(image).convert('RGBA')
                prepared.thumbnail((512,512), Image.Resampling.LANCZOS)
                clean = Image.new('RGBA', prepared.size)
                clean.paste(prepared)
                output = io.BytesIO(); clean.save(output,format='PNG')
                return output.getvalue()
    except (OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError('That image could not be safely opened') from None
