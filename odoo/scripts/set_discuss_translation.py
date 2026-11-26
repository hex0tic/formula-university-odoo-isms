"""Apply the Formula University Mongolian labels through `odoo shell`."""

from lxml import etree


LANG = 'mn_MN'
LABEL = 'Хэлэлцэх'
LABELS = (
    ('mail.menu_root_discuss', 'name', 'Discuss'),
    ('mail.mail_menu_technical', 'name', 'Discuss'),
    ('mail.action_discuss', 'name', 'Discuss'),
    ('base.module_mail', 'shortdesc', 'Discuss'),
    ('base.module_category_productivity_discuss', 'name', 'Discuss'),
    ('mail.mt_comment', 'name', 'Discussions'),
)


def apply_discuss_translation(env):
    for xmlid, field, source in LABELS:
        record = env.ref(xmlid)
        if record.with_context(lang='en_US')[field] != source:
            raise ValueError(f'Unexpected English label for {xmlid}')
        if record.with_context(lang=LANG)[field] != LABEL:
            record.update_field_translations(field, {LANG: LABEL})
        if record.with_context(lang=LANG)[field] != LABEL:
            raise ValueError(f'Translation was not applied for {xmlid}')

    view = env.ref('mail.res_config_settings_view_form')

    def settings_title(lang):
        arch = etree.fromstring(view.with_context(lang=lang).arch_db.encode())
        return arch.xpath('string(//block[@id="discuss"]/@title)')

    if settings_title('en_US') != 'Discuss':
        raise ValueError('Unexpected English Discuss settings title')
    if settings_title(LANG) != LABEL:
        view.update_field_translations('arch_db', {LANG: {'Discuss': LABEL}})
    if settings_title(LANG) != LABEL:
        raise ValueError('Discuss settings translation was not applied')


apply_discuss_translation(env)
env.cr.commit()
env.registry.signal_changes()
print(f'{LANG}: {LABEL} ({len(LABELS)} labels and the settings title)')
