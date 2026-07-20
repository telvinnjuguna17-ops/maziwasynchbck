from rest_framework import serializers

from core.models import Feedback, MilkCollection

# serilaizer for the farmer milk collection showing also the porter who also collected the milk
class MilkCollectionSerializer(serializers.ModelSerializer):
    porter_name=serializers.SerializerMethodField()
    class Meta:
        model=MilkCollection
        fields=['id','liters','session','price_per_liter','total_amount','collection_date','porter']

    # method to just join the first and the last name of the porter to be just one name
    # use it when you want to alter the field on how it look like in the model    
    def get_porter_name(self,obj):
        return f"{obj.porter.first_name} {obj.porter.last_name}"  

# feedback serializer
class FeedBackSerializer(serializers.ModelSerializer):
    class Meta:
        model=Feedback
        fields=['id','title','description','status','created_at','updated_at']
        read_only_fields=['status','created_at','updated_at']     
      