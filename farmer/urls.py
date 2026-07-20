from django.urls import path,include
from farmer import views
from rest_framework.routers import DefaultRouter




router=DefaultRouter()
router.register('feedback',views.FeedbackViewset,basename='feedback')
urlpatterns = [
    path('collections/', views.FarmerCollection.as_view()),
    path('dashboard/', views.Farmerdashboard.as_view()),
    path('predict/',views.PredictDisease),

     path('', include(router.urls))

    

    
]
