from django.db import models
class DustbinCity(models.Model):
    city = models.CharField(max_length=159)


class Zone(models.Model):
    name = models.CharField(max_length=144)
    city = models.ForeignKey(DustbinCity, on_delete=models.CASCADE)


class DetectImages(models.Model):
    name = models.CharField(max_length=255)
    related_zone = models.ForeignKey(Zone, on_delete=models.CASCADE)

    is_dustbin_fill_in_start_top_view = models.ImageField(upload_to='uploads/')
    is_dustbin_fill_in_start_top_view_ok = models.BooleanField(default=False)

    is_any_trash_detected_near_dustbin = models.ImageField(upload_to='uploads/')
    is_any_trash_detected_near_dustbin_ok = models.BooleanField(default=False)

    after_removing_trash_from_inside = models.ImageField(upload_to='uploads/')
    after_removing_trash_from_inside_ok = models.BooleanField(default=False)

    after_removed_trash_near_from_dustbin = models.ImageField(upload_to='uploads/')
    after_removed_trash_near_from_dustbin_ok = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
