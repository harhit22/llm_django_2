from django.db import models


# Create your models here.

class SopQNA(models.Model):
    question = models.TextField()
    sop_answer = models.TextField()


class City(models.Model):
    city = models.CharField(max_length=255)
    sop_status = models.BooleanField(default=True)

class Sops(models.Model):
    STATUS_CHOICES = [
        ('operation', 'operation'),
        ('maintenance', 'Maintenance'),
    ]
    cities = models.ManyToManyField(City, related_name="sops" , blank=True, null=True)
    department = models.CharField(max_length=255, choices=STATUS_CHOICES, default='operation')
    action_owner = models.CharField(max_length=255)
    sop = models.CharField(max_length=255)
    topics = models.CharField(max_length=255)
    vertical = models.CharField(max_length=255)
    training_and_task_start = models.DateTimeField()
    action_step = models.TextField(null=True, blank=True)
    Deadline_1 = models.CharField(max_length=255, null=True, blank=True)
    assessment_1 = models.TextField(null=True, blank=True)
    Deadline_2 = models.CharField(max_length=255, null=True, blank=True)
    assessment_2 = models.TextField(null=True, blank=True)

    team_assessment = models.TextField(null=True, blank=True)
    no_of_deadline = models.IntegerField(null=True, blank=True)
    total_sop_step = models.IntegerField()
    done_sop_step_number = models.IntegerField()
    sop_percentage = models.FloatField(null=True, blank=True)
    frequency = models.CharField(max_length=255)
    in_working = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.action_owner:
            last_sop = Sops.objects.all().order_by('-id').first()
            if last_sop and last_sop.action_owner and last_sop.action_owner.startswith('sop_'):
                try:
                    last_number = int(last_sop.action_owner.split('_')[1])
                except (IndexError, ValueError):
                    last_number = 0
            else:
                last_number = 0
            self.action_owner = f'sop_{last_number + 1}'
        super().save(*args, **kwargs)


class SopStep(models.Model):
    sop = models.ForeignKey(Sops, on_delete=models.CASCADE, related_name="steps")
    step_number = models.IntegerField()
    description = models.TextField()



