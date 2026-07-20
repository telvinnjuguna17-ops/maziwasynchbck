from rest_framework import serializers

from core.models import FarmerProfile, MilkCollection, Notice, PorterProfile

# admin/cooperative farmer account
class FarmerSerializer(serializers.ModelSerializer):
    class Meta:
        model=FarmerProfile
        fields='__all__'

# admin/cooperative account for porter account
class PorterSerializer(serializers.ModelSerializer):
    class Meta:
        model=PorterProfile
        fields='__all__'

#admin/cooperative acount for the milkcollection account
class MilkCollectionSerializer(serializers.ModelSerializer):
    class Meta:
        model=MilkCollection
        fields='__all__'        


#Notices
class NoticeSerializer(serializers.ModelSerializer):
    class Meta:
        model=Notice
        fields='__all__'
        read_only_field=['created_by']