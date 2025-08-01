# Generated by Django 4.2.23 on 2025-07-24 15:54

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='RouteMonthlyStat',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('origin_code', models.CharField(blank=True, help_text='出发城市三字码', max_length=10, null=True)),
                ('destination_code', models.CharField(blank=True, help_text='到达城市三字码', max_length=10, null=True)),
                ('year', models.IntegerField(help_text='年份')),
                ('month', models.IntegerField(help_text='月份')),
                ('passenger_volume', models.FloatField(help_text='航线总客运量（万人次）')),
                ('Route_Total_Seats', models.FloatField(help_text='航线总座位数（座位）')),
                ('Route_Total_Flights', models.IntegerField(help_text='航线总航班数量（班次）')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': '航线月度统计',
                'verbose_name_plural': '航线月度统计',
                'ordering': ['-year', '-month'],
                'unique_together': {('origin_code', 'destination_code', 'year', 'month')},
            },
        ),
    ]
