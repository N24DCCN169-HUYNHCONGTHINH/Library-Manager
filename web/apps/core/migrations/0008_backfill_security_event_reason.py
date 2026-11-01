from django.db import migrations


def copy_existing_reasons(apps, schema_editor):
    AccountSecurityEvent = apps.get_model("core", "AccountSecurityEvent")
    alias = schema_editor.connection.alias
    events = AccountSecurityEvent.objects.using(alias).only("pk", "details", "reason").iterator()
    for event in events:
        if not event.reason and isinstance(event.details, dict):
            reason = event.details.get("reason")
            if isinstance(reason, str) and reason.strip():
                AccountSecurityEvent.objects.using(alias).filter(pk=event.pk).update(reason=reason[:300])


class Migration(migrations.Migration):
    dependencies = [("core", "0007_accountsecurityevent_reason")]

    operations = [migrations.RunPython(copy_existing_reasons, migrations.RunPython.noop)]
