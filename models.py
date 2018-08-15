from django.db import models


class Machines(models.Model):
    ip_address = models.GenericIPAddressField(unique=True)
    description = models.CharField(max_length=200, default="-")
    community_name = models.CharField(max_length=32, default="pash")
    remote_as = models.IntegerField(default="65001")
    login = models.CharField(max_length=64, default="pashorg")
    password = models.CharField(max_length=64, default="")
    enable_password = models.CharField(max_length=64, default="privet")

    def __str__(self):
        return self.description + "; ip: " + self.ip_address


class Interfaces(models.Model):
    m = models.ForeignKey(Machines, on_delete=models.CASCADE)
    name = models.CharField(max_length=200, default='-')
    ip_address = models.GenericIPAddressField()
    description = models.CharField(max_length=200)
    snmp_number = models.IntegerField()
    max_in = models.FloatField()
    max_out = models.FloatField()
    enable = models.BooleanField(default=False)
    rm_id = models.IntegerField(null=True, blank=True, default=None, unique=True)

    def __str__(self):
        return self.description + "; ip: " + self.ip_address

    class Meta:
        unique_together = ("m", "name")


class Stats(models.Model):
    i = models.ForeignKey(Interfaces, on_delete=models.CASCADE)
    counter_in = models.BigIntegerField()
    counter_out = models.BigIntegerField()
    timestamp = models.DateTimeField(auto_now=False, auto_now_add=True)

    def __str__(self):
        return "Counters on " + self.ip_address + " at " + self.timestamp


class RouteMaps(models.Model):
    m = models.ForeignKey(Machines, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    community = models.CharField(default='0', max_length=11)

    def __str__(self):
        return self.name

    class Meta:
        unique_together = ("m", "name")


class Neighbours(models.Model):
    rm_in = models.IntegerField()
    rm_out = models.ForeignKey(RouteMaps, on_delete=models.CASCADE)
    i = models.ForeignKey(Interfaces, on_delete=models.CASCADE)
    ip_address = models.GenericIPAddressField()

    def __str__(self):
        return self.ip_address


class Settings(models.Model):
    net = models.GenericIPAddressField()
    net_mask = models.IntegerField()
    max_prepend = models.IntegerField(default=5)
    max_prefix = models.IntegerField(default=22)
    m = models.ForeignKey(Machines, on_delete=models.CASCADE)
    nexthop = models.GenericIPAddressField(null=True, blank=True, default=None)
    quagga_seq = models.IntegerField(default=1)

    class Meta:
        unique_together = ("m", "net")


class PrefixLists(models.Model):
    m = models.ForeignKey(Machines, on_delete=models.CASCADE)
    s = models.ForeignKey(Settings, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    net = models.GenericIPAddressField()
    net_mask = models.IntegerField()
    rm_seq = models.IntegerField()

    def __str__(self):
        return "Prefix-List" + self.name + " " + self.ip_subnet + "/" + self.ip_mask

    class Meta:
        unique_together = ("m", "name")


class RMtoPL(models.Model):
    rm = models.ForeignKey(RouteMaps, on_delete=models.CASCADE)
    prepend = models.IntegerField(default=0)
    pl = models.ForeignKey(PrefixLists, on_delete=models.CASCADE, default=1)

    def __str__(self):
        return "RM " + str(self.rm_id) + "-PL " + str(self.pl_id)

    class Meta:
        unique_together = ("rm", "pl")


class DoNotDistribute(models.Model):
    ip_address = models.GenericIPAddressField(unique=True)

    def __str__(self):
        return str(self.ip_address)

