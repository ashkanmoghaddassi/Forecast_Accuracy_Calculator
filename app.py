from flask import Flask, render_template, request
import pandas as pd
import numpy as np
import collections
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from io import BytesIO
import base64

app = Flask(__name__)

# Global variables to store data and messages
processed_data = None
success_message = None
count_column1 = None
median_column2 = None
plot_data = None
success_message1 = None
success_message2 = None
statistics = None
out = None 
def process_csv(file_path):
    global success_message, count_column1, median_column2, plot_data, success_message1, success_message2, statistics,out

   
    data = pd.read_csv(file_path)
    df = pd.DataFrame(data=data)


    times_dict = collections.defaultdict(list)
    x = 0
    for cust in df['INST_ID']:
        times_dict[cust].append(df.iloc[x]['ON_DATE_TIME'])
        #sort list of times for each customer
        times_dict[cust].sort()
        x+=1


    old_time = 0
    pred_time = df.iloc[0]['PREDICTED_AMOUNT_DATE_TIME_2']
    rates = collections.defaultdict(list)
    incomplete_customers = collections.defaultdict(int)

    for cust in times_dict:
        for i in range(len(times_dict[cust])):
    
            time1=times_dict[cust][i]
            ir = False
            incomplete_reading = df.loc[(df['INST_ID']==cust) & (df['ON_DATE_TIME']==time1)]['INCOMPLETE_READING']
            incomplete_reading = incomplete_reading.iloc[0]
            
            #adding flag if any incomplete readings
            if incomplete_reading == 'Y':
                ir = True
                incomplete_customers[cust] = 1

        
            #when there is a reading 12pm (i.e. pred_time), we save it and break out of the loop
            if time1==pred_time and not ir:
                actual = df.loc[(df['INST_ID']==cust) & (df['ON_DATE_TIME']==pred_time)]['INST_PRODUCT_AMOUNT']
                rates[cust] = [actual.iloc[0],time1]
                break

            #if reading is very close to 12 (and no reading exactly at 12), save it and break out of loop
            elif (pred_time-.001)<=time1<=(pred_time+.001)and pred_time not in times_dict[cust] and not ir:
                actual = df.loc[(df['INST_ID']==cust) & (df['ON_DATE_TIME']==time1)]['INST_PRODUCT_AMOUNT']
                rates[cust] = [actual.iloc[0],time1]
                break
        
            #if the first reading is after 12 then we can't estimate an amount for this customer and break out of the loop
            elif time1>pred_time and i==0:
                break  
            
            #if reading after 12 and has previous reading before 12pm we can acquire our upper and lower bounds for that customer 
            elif time1>pred_time and not ir:
                upper_bound,upper_amt = time1, df.loc[(df['INST_ID']==cust) & (df['ON_DATE_TIME']==time1)]['INST_PRODUCT_AMOUNT'].to_numpy()
                lower_bound,lower_amt = old_time, df.loc[(df['INST_ID']==cust) & (df['ON_DATE_TIME']==old_time)]['INST_PRODUCT_AMOUNT'].to_numpy()
            
            #If the second reading is a delivery, we subtract the amount delivered to calculate the usage rate. Note second reading is after 12, therefore it won't 
                amount_delivered = 0 
                reading_source, status = df.loc[(df['INST_ID']==cust) & (df['ON_DATE_TIME']==time1)]['READING_SOURCE'], df.loc[(df['INST_ID']==cust) & (df['ON_DATE_TIME']==time1)]['STATUS']
                forecasted = df.loc[(df['INST_ID']==cust) & (df['ON_DATE_TIME']==time1)]['PREDICTED_AMOUNT_2']
                forecasted = int(forecasted.iloc[0])

                if reading_source.iloc[0] == 'D' and status.iloc[0] == 'D':
                    amount_delivered = df.loc[(df['INST_ID']==cust) & (df['ON_DATE_TIME']==time1)]['ACTUAL_AMOUNT'].to_numpy()
                    amount_delivered = int(amount_delivered[0])
                    upper_amt = pd.array([int(upper_amt[0]) - amount_delivered])
                    
                    


                minutes_diff = (upper_bound-lower_bound) * 1440
                usage_rate = (int(upper_amt[0])-int(lower_amt[0]))/minutes_diff
                
                rates[cust] = [upper_bound,lower_bound,int(upper_amt[0]),int(lower_amt[0]),usage_rate,amount_delivered]
                break

            elif ir:
                break
            
            old_time = time1

            
            
        #we calculate the projected amount for customers who have readings before and after 12pm. i.e. the customer is in the rates dictionary and has upper and lower bounds     
        if cust in rates and len(rates[cust])>2: 
        

            minutes_to_forecast = (pred_time-lower_bound)*1440
            projected_amount = lower_amt[0]+(minutes_to_forecast*rates[cust][4])
            rates[cust].append(minutes_to_forecast)
            rates[cust].append(float(projected_amount))



    accuracy = collections.defaultdict(list)
    for cust in rates.keys():
        if incomplete_customers[cust] == 1:
            incomplete_flag = 'Y'
        else:
            incomplete_flag = 'N'
            
        if len(rates[cust])==2:
            forecasted = df.loc[(df['INST_ID']==cust) & (df['ON_DATE_TIME']==rates[cust][1])]['PREDICTED_AMOUNT_2']
            actual = rates[cust][0]
            first, second = 0,0
            first_time, second_time = rates[cust][1],rates[cust][1]
            amt_deliv = 0 
        else:
            actual = rates[cust][7]
            forecasted = df.loc[(df['INST_ID']==cust) & (df['ON_DATE_TIME']==rates[cust][0])]['PREDICTED_AMOUNT_2']
            first, second = rates[cust][3], rates[cust][2]
            first_time, second_time = rates[cust][1],rates[cust][0]
            amt_deliv = rates[cust][5]
        
        
            
        
        forecasted = int(forecasted.iloc[0])
        percent_error = abs((actual-forecasted)/actual)*100
        accuracy["Customer"].append(cust)
        accuracy["Forecasted"].append(forecasted)
        accuracy["Est. Actual Amount"].append(float(actual))
        accuracy["1st Reading"].append(float(first))
        accuracy["2nd Reading"].append(float(second))
        accuracy["1st Time"].append(first_time)
        accuracy["2nd Time"].append(second_time)
        accuracy["PctError"].append(float(percent_error))
        accuracy["Delivered Amount"].append(int(amt_deliv)) 
        accuracy["Has Incomplete Readings"].append(incomplete_flag)


    out = pd.DataFrame(accuracy)

    statistics = out.describe()

    # Extract count and median for specific columns
    count_column1 = statistics.loc['count', 'Customer']  # Replace 'column1' with the name of the column you want count for
    median_column2 = statistics.loc['50%', 'PctError']  # Replace 'column2' with the name of the column you want median for


    return (int(count_column1),round(median_column2,3))
def export():
    global out
    file_name = 'Accuracy_Results_TEST.xlsx'
    # saving the excel
    out.to_excel(file_name)

# This function should contain your visualization logic
def visualize_statistics():
    # Your visualization logic here
    # This function should return the plot data
    global statistics
    # Generate Seaborn line plot
    statistics = statistics.drop('count')
    statistics.reset_index(inplace=True)
    plt.figure(figsize=(8, 6))
    sns.lineplot(x="index", y="PctError", data=statistics, markers=True, marker='o')

    # Adding value annotations
    x, y = statistics['index'], statistics['PctError']
    for i, txt in enumerate(y):
        plt.annotate(round(txt, 3), (x[i], y[i]), textcoords="offset points", xytext=(0, 4), ha='center')

    plt.xlabel('')
    plt.ylabel('Percent Error')

    # Save the plot to a bytes buffer
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    plot_data = base64.b64encode(buffer.getvalue()).decode()

    # Close the plot to free memory
    plt.close()

    return plot_data

def index():
    global success_message, count_column1, median_column2, plot_data, success_message1, success_message2, statistics,out
    return render_template('index.html', statistics = statistics, out = out, success_message=success_message, count_column1=count_column1, median_column2=median_column2, plot_data=plot_data, success_message1=success_message1, success_message2=success_message2)

@app.route('/')
def index1():
    global success_message, count_column1, median_column2, plot_data, success_message1, success_message2, statistics,out
    success_message = None
    count_column1 = None
    median_column2 = None
    plot_data = None
    success_message1 = None
    success_message2 = None
    statistics = None
    out = None 
    return render_template('index.html', statistics = statistics, out = out, success_message=success_message, count_column1=count_column1, median_column2=median_column2, plot_data=plot_data, success_message1=success_message1, success_message2=success_message2)


@app.route('/run_script', methods=['POST'])
def run_script():
    global success_message, count_column1, median_column2, plot_data, success_message1, success_message2, out,statistics

    csv_file = request.form['file']
    med_count = process_csv(csv_file)
     
     # Calculate count of column1 and median of column2
    count_column1,median_column2 = med_count[0],str(med_count[1])+'%'
    success_message = "Statistics calculated successfully."

    return index()
        
@app.route('/visualize_statistics', methods=['POST'])
def visualize_stats():
    global success_message, count_column1, median_column2, plot_data, success_message1, success_message2,statistics, out

    plot_data = visualize_statistics()
    success_message1 = "Statistics visualized successfully."
    return index()

@app.route('/export', methods=['POST'])
def export_to_excel():
    global success_message, count_column1, median_column2, plot_data, success_message1, success_message2,statistics, out

    export()
    success_message2 ="Exported Details to an Excel File"
    return index()

@app.route('/clear', methods=['POST'])
def clear():
    global success_message, count_column1, median_column2, plot_data, success_message1, success_message2, out, statistics
    # Global variables to store data and messages
    success_message = None
    count_column1 = None
    median_column2 = None
    plot_data = None
    success_message1 = None
    success_message2 = None
    statistics = None
    out = None 

    return index()



if __name__ == '__main__':
    app.run(debug=True)
