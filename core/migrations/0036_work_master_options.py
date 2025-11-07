from django.db import migrations, models


def create_work_master_defaults(apps, schema_editor):
    Category = apps.get_model('core', 'WorkCategoryOption')
    Warranty = apps.get_model('core', 'WorkWarrantyOption')
    JobType = apps.get_model('core', 'WorkJobTypeOption')
    DthType = apps.get_model('core', 'WorkDthTypeOption')
    FiberType = apps.get_model('core', 'WorkFiberTypeOption')
    FrIssue = apps.get_model('core', 'WorkFrIssueOption')

    defaults = {
        Category: [
            ('dth', 'DTH', 1),
            ('fiber', 'Air Fiber', 2),
        ],
        Warranty: [
            ('in', 'In Warranty', 1),
            ('out', 'Out of Warranty', 2),
        ],
        JobType: [
            ('fr', 'Field Repair', 1),
            ('reinstallation', 'Reinstallation', 2),
            ('deinstallation', 'Deinstallation', 3),
            ('retrieval', 'Retrieval', 4),
        ],
        DthType: [
            ('fullset', 'Full Set', 1),
            ('box', 'Box Only', 2),
        ],
        FiberType: [
            ('with_iptv', 'With IPTV', 1),
            ('without_iptv', 'Without IPTV', 2),
        ],
        FrIssue: [
            ('box', 'Box Issue', 1),
            ('signal', 'Signal Issue', 2),
        ],
    }

    for model, entries in defaults.items():
        for code, name, ordering in entries:
            model.objects.update_or_create(
                code=code,
                defaults={
                    'name': name,
                    'ordering': ordering,
                    'is_active': True,
                }
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0035_handsetcollection_handsetpurchase_handsetstock_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkCategoryOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=50, unique=True)),
                ('name', models.CharField(max_length=120)),
                ('description', models.TextField(blank=True)),
                ('ordering', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['ordering', 'name']},
        ),
        migrations.CreateModel(
            name='WorkDthTypeOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=50, unique=True)),
                ('name', models.CharField(max_length=120)),
                ('ordering', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['ordering', 'name']},
        ),
        migrations.CreateModel(
            name='WorkFiberTypeOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=50, unique=True)),
                ('name', models.CharField(max_length=120)),
                ('ordering', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['ordering', 'name']},
        ),
        migrations.CreateModel(
            name='WorkFrIssueOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=50, unique=True)),
                ('name', models.CharField(max_length=120)),
                ('ordering', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['ordering', 'name']},
        ),
        migrations.CreateModel(
            name='WorkJobTypeOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=50, unique=True)),
                ('name', models.CharField(max_length=120)),
                ('description', models.TextField(blank=True)),
                ('ordering', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['ordering', 'name']},
        ),
        migrations.CreateModel(
            name='WorkWarrantyOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=50, unique=True)),
                ('name', models.CharField(max_length=120)),
                ('description', models.TextField(blank=True)),
                ('ordering', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['ordering', 'name']},
        ),
        migrations.AlterField(
            model_name='workstb',
            name='category',
            field=models.CharField(default='dth', max_length=50),
        ),
        migrations.AlterField(
            model_name='workstb',
            name='dth_type',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='workstb',
            name='fiber_type',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='workstb',
            name='fr_issue',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='workstb',
            name='job_type',
            field=models.CharField(default='fr', max_length=50),
        ),
        migrations.AlterField(
            model_name='workstb',
            name='warranty',
            field=models.CharField(default='out', max_length=50),
        ),
        migrations.RunPython(create_work_master_defaults, noop_reverse),
    ]

