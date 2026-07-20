from django.shortcuts import render
from rest_framework import generics,viewsets
from rest_framework.permissions import IsAuthenticated,AllowAny
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView

from collector.serializer import MilkCollectionSerializer
from core.models import FarmerProfile, Feedback, MilkCollection
from farmer.serializer import FeedBackSerializer
from django.db.models import Sum
from datetime import date
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.decorators import api_view,permission_classes

from farmer.services import CattleAIService

# Create your views here.

# Farmer's Dashboard
class Farmerdashboard(APIView):
    permission_classes=[IsAuthenticated]
    def get(self,request):
        farmer=request.user.farmer_profile
        collection=MilkCollection.objects.filter(farmer=farmer)
        total_collections=collection.count()
        total_liters=collection.aggregate(total=Sum('liters'))['total'] or 0
        total_amount=collection.aggregate(total=Sum('total_amount'))['total'] or 0

        today_collection=collection.filter(collection_date=date.today()).aggregate(total=Sum('liters'))['total'] or 0

        monthly_liters=collection.filter(
            collection_date__month=timezone.now().month
        ).aggregate(total=Sum('liters'))['total'] or 0

        monthly_earnings=collection.filter(
            collection_date__month=timezone.now().month

        ).aggregate(total=Sum('total_amount'))['total'] or 0


        return Response({
            "total_collections":total_collections,
            "total_liters":total_liters,
            "total_amount":total_amount,
            "today_collection":today_collection,
            "monthly_liters":monthly_liters,
            "monthly_earnings":monthly_earnings
        })



# farmer's milk collection
class FarmerCollection(generics.ListAPIView):
    serializer_class=MilkCollectionSerializer
    permission_classes=[IsAuthenticated]

    #query set- where we fetch data from the model in the class
    def get_queryset(self):
        try:
            farmer=self.request.user.farmer_profile
        except FarmerProfile.DoesNotExist:
            raise PermissionDenied(
                "Only farmers can access this endpoint"
            )
        collections=(
            MilkCollection.objects
            .filter(farmer=farmer)
            .select_related('porter')
            .order_by('created_at')
        )

        return collections
    


# ===================================
# Feedback CRUD-> viewsets
# ===================================
class FeedbackViewset(viewsets.ModelViewSet):
    serializer_class=FeedBackSerializer
    permission_classes=[IsAuthenticated]
    # This is for the GET request
    def get_queryset(self):
        try:
            farmer=self.request.user.farmer_profile
        except:
            raise PermissionDenied("Only Farmers can access this endpoint")
        
        feedback=(
            Feedback.objects
            .filter(farmer=farmer)
            .order_by('created_at')
        )
        return feedback
    
    # post by the farmer
    def perform_create(self, serializer):
        try:
            farmer=self.request.user.farmer_profile
        except:
            raise PermissionDenied("Only Farmers can give a feedback")
        
        serializer.save(farmer=farmer)
        
# cattleai function
@ api_view(["POST"])
@permission_classes([IsAuthenticated])
def PredictDisease(request):
    animal=request.data.get('Animal')
    age=request.data.get('Age')
    temp=request.data.get('Temperature')
    Description=request.data.get('Description')


    # create our ai object from the CattleAIService
    ai_service=CattleAIService()
    result=ai_service.predict(animal_type=animal,age=age,temp=temp,description=Description)
    return Response(result)          