import json
# from loguru import logger
# from aera import session
from datetime import datetime
import warnings
import pandas as pd
import math
import calendar
import requests
from dateutil.relativedelta import relativedelta

warnings.filterwarnings("ignore")

def ConstrainedPlan(req_prod,capacity,production,inventory,sales,dos,pullin_desired_order, pushout_desired_order,doh_floor_ceil_df1):
    print('\n Constrained Plan pullin_desired_order  ',pullin_desired_order,'and pushout_desired_order ', pushout_desired_order )
                
    req_prod = req_prod.drop(req_prod.columns[3:5], axis=1)
    month_list_invt = list(capacity.columns)
    capacity = capacity.drop(capacity.columns[:2], axis=1)
    production = production.drop(production.columns[3:5], axis=1)
    
    
    last_month_invt = inventory.iloc[:, [0, 1, 2, 4]]
    inventory = inventory.drop(inventory.columns[3:5], axis=1)
    sales = sales.drop(sales.columns[3:5], axis=1)
    dos = dos.drop(dos.columns[3:5], axis=1)
    
    # print('DOS :', dos.columns)
    total_production = req_prod.sum(axis = 0, numeric_only = True)
    # print('total_production :', total_production)
    difference = capacity.subtract(total_production[capacity.columns])
    # print('difference :', difference)
    diff_dict = difference.to_dict()
    all_data = {key: value[0] for key, value in diff_dict.items()}
    all_keys = list(all_data.keys())
    ###### Printing orignal datframes
    # production.to_csv('production_orignal.csv', index = False)
    # req_prod.to_csv('req_production_orignal.csv', index = False)
    # capacity.to_csv('capacity_orignal.csv', index = False)
    # total_production.to_csv('total_production_orignal.csv', index = False)
    #sales.to_csv('sales_orignal.csv', index = False)
    # dos.to_csv('dos_orignal.csv', index = False)
    #inventory.to_csv('inventory_orignal.csv', index = False)
    def days_in_month(month_str):
        # Parse the month and year from the input string
        month_abbr, year = month_str.split()
        year = int(year)
        
        # Convert month abbreviation to month number (1 for January, 2 for February, etc.)
        month_num = list(calendar.month_abbr).index(month_abbr)
        
        # Use calendar.monthrange to get the number of days
        _, num_days = calendar.monthrange(year, month_num)
        
        return num_days
    
    def calculate_amt_of_invt(floor_doh, sales_forecast, days_per_month):
        remaining_days = floor_doh
        amt_of_invt = 0
        for sales, days in zip(sales_forecast, days_per_month): # apr, may, jun - rem_days = 150
            if remaining_days >= days:
                # Add the full month's sales to inventory if the days cover the full month
                amt_of_invt += sales
                remaining_days -= days
            else:
                # Add partial sales for the remaining days
                amt_of_invt += (remaining_days / days) * sales
                break  # Requirement met, break the loop
        # Round up to the nearest integer
        return math.ceil(amt_of_invt)
    def calculate_days_of_supply(end_of_month_inventory, sales_forecast,days_per_month):
        import math
        # Initialize variables
        remaining_inventory = end_of_month_inventory
        total_days_of_supply = 0
        sale_frcst = []
        for sale, days in zip(sales_forecast, days_per_month):
            # Check if inventory can cover full month
            if remaining_inventory >= sale and remaining_inventory!=0:
                total_days_of_supply += days
                remaining_inventory -= sale
                sale_frcst.append(sale)
            
            else:
                # Calculate partial month days if inventory is less than the sales forecast
                partial_days = round((remaining_inventory / sale) * days,2)
                total_days_of_supply += partial_days
                break
            
        # to handle consecative zero sales forecast entries
        if len(sale_frcst)== 2:
            if sale_frcst[0]+sale_frcst[1] == 0:
                total_days_of_supply = days_per_month[0] + days_per_month[1]
        if len(sale_frcst)> 2:
            if sale_frcst[1]+sale_frcst[2] == 0:
                total_days_of_supply = days_per_month[0] + days_per_month[1]
            
        return total_days_of_supply
    
    def update_inventory(sublist,car_model,model_year,prev_month):
        #if production month_beg of last month
        #sub = [mar 25, apr 25]
        if sublist[0] == inventory.columns[3]:
            prev_month_invt = last_month_invt.loc[(inventory['PRODUCT_TRIM'] == car_model) & (inventory['MODEL_YEAR'] == model_year), prev_month]
        else:
            prev_month_invt = inventory.loc[(inventory['PRODUCT_TRIM'] == car_model) & (inventory['MODEL_YEAR'] == model_year), prev_month]
        i = 0
        #sublist= [dec,jan,feb] 
        for month in sublist:
            #iteration dec: , prev month = nov, i = 0,
            #iteration 2 jan: prev month = dec, i =1
            if i>=1:
                prev_month = sublist[i-1]
                prev_month_invt = inventory.loc[(inventory['PRODUCT_TRIM'] == car_model) & (inventory['MODEL_YEAR'] == model_year), prev_month]
            i+=1
            inventory.loc[(inventory['PRODUCT_TRIM'] == car_model) & (inventory['MODEL_YEAR'] == model_year), month] =  prev_month_invt + production.loc[(production['PRODUCT_TRIM'] == car_model) & (production['MODEL_YEAR'] == model_year), month] - sales.loc[(sales['PRODUCT_TRIM'] == car_model) & (sales['MODEL_YEAR'] == model_year), month]
   
    def update_value_pull(pull_value, car_model, add_month, sub_month, model_year):
        # Define a helper function for updates to avoid redundancy
        def update_data(df, model_col, year_col):
            # Check if the car model and MODEL_YEAR exist in the DataFrame
            if car_model in df[model_col].values:
                if add_month in df.columns:
                    pass  # Placeholder for logic
                if sub_month in df.columns:
                    pass  # Placeholder for logic
            # Assuming car_model, model_year, model_col, year_col, and month_plus1 are defined
            value = df.loc[(df[model_col] == car_model) & (df[year_col] == model_year), sub_month].values[0]
            print("update production: ", df.loc[(df[model_col] == car_model) & (df[year_col] == model_year), sub_month])
            if value<0:
                print("--------------------------negative production found for pull------------------------------")
        # Update production and inventory data with the added MODEL_YEAR condition
        update_data(production, "PRODUCT_TRIM", "MODEL_YEAR")
    def update_value_push(push_value, car_model, add_month, sub_month, model_year):
    # Define a helper function for updates to avoid redundancy
        def update_data(df, model_col, year_col):
            # Check if the car model and MODEL_YEAR exist in the DataFrame
            if car_model in df[model_col].values:
                if add_month in df.columns:
                    pass  # Placeholder for logic
                if sub_month in df.columns:
                    pass  # Placeholder for logic
            # Assuming car_model, model_year, model_col, year_col, and month_plus1 are defined
            value = df.loc[(df[model_col] == car_model) & (df[year_col] == model_year), sub_month].values[0]
            print("update production: ", df.loc[(df[model_col] == car_model) & (df[year_col] == model_year), sub_month])
            if value<0:
                print("--------------------------negative production found for push------------------------------")
        # Update production and inventory data with the added MODEL_YEAR condition
        update_data(production, "PRODUCT_TRIM", "MODEL_YEAR")
    def generate_month_list(year):
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        month_list = [f"{month} {year}" for month in months]
        return month_list
    def next_two_months(month_list):
        # Define the month names and their corresponding next months
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        # Get the last entry in the list
        last_entry = month_list[-1]
        last_month, last_year = last_entry.split()
        last_year = int(last_year)  # Convert year to integer
        # Find the index of the last month
        last_month_index = months.index(last_month)
        # Prepare the next two months
        next_months = []
        for i in range(2):
            next_month_index = (last_month_index + 1 + i) % 12  # Wrap around using modulo
            next_year = last_year + (last_month_index + 1 + i) // 12  # Increment year if needed
            next_months.append(f"{months[next_month_index]} {next_year}")
        # Add the new months to the original list
        return next_months
    def find_common_elements_ordered(list1, list2):
        # Create a set from the second list for faster lookup
        set_list2 = set(list2)
        # Use a list comprehension to maintain order from list1
        common_elements = [item for item in list1 if item in set_list2]
        return common_elements
    # just extarct what year data is present
    def extract_years(month_year_list):
        years = set()  # Use a set to avoid duplicates
        for item in month_year_list:
            # Split the string and get the year part
            year = item.split()[1]
            years.add(year)
        return list(years)
    years_present = extract_years(all_keys)
    years_present = sorted(years_present)
    # print('years_present :', years_present)
    for year_num in years_present:
        yr_month_list = generate_month_list(year_num)
        actual_data_present = find_common_elements_ordered(yr_month_list, all_keys)
        actual_data_present_v0 = actual_data_present
                    
        # Check if the iteration is for last year
            # If yes apply following conditions for last year
                # 1. Target and current month cannot touch last 2 months of that year : +2 months sales value reliance
                    #thus the year data itself should have more than 2 months of data for any balancing iterations
                # 2. No 3rd iteration sweep 
        is_final_year = 0
        year_num = int(year_num) 
        # print('Last year check year_num' , year_num,type(year_num),'and int(years_present[-1])', int(years_present[-1]))
        # print('first iteration actual_data_present before condition',actual_data_present, len(actual_data_present))
        if year_num == int(years_present[-1]):
            # print('inside last year check')
            is_final_year = 1
            if len(actual_data_present) >= 4:
                # print('actual data length check ')
                actual_data_present = actual_data_present[:-2]
                
            else:
                # print('\n \n *** Last year doesn\'t have data more than 3 months , thus planning operation canot be executed ! ***')
                break
        
        # print('actual_data_present After condition',actual_data_present)
            
        # create data dictionary .i.e. surplus/deficit data from orignal dictionary based on the calender year cut
        # give access to plus 2 months from end but iteration alwasy end at dec
        data = {key: all_data[key] for key in actual_data_present if key in all_data}
        keys = list(data.keys()) 
        # print(data)
        # extend the plus two months as special key data for inventory
        inv_next_two_month = next_two_months(actual_data_present)
        special_inv_month_key = actual_data_present+inv_next_two_month
        # print('1st iteration actual_data_present',actual_data_present)
        # print('1st iteration special_inv_month_key',special_inv_month_key)
        ##################################################### 1st  Surplus iteration #########################################
        # print('\n\n##################################################### 1st  Surplus iteration #########################################')
        sweep_iteration_flag = 0
        for i, month in enumerate(keys):
        
            surplus = data[month]
            # defining a variable to differentiate between current and target month
            curr_month_num = i
            curr_month = keys[curr_month_num]    
            if keys[i] == list(all_data.keys())[-1]:
                # print(f"Reached end of Given production data - {keys[i]}....closing operation")
                break
            if surplus>0:
                # print("\n\n--- Month {}, surplus {} ---".format(keys[curr_month_num],surplus))
                ###### condition to stop on dec
                if ('Dec' in keys[curr_month_num]) :
                    # print('**No pull in /push out allowed on Jan for firs two iteration...closing operation***')
                    break        
                        
                while surplus > 0:
                    # TODO: Implement logic to resolve surplus here
                    # For now, break to avoid infinite loop and satisfy indentation
                    break
        ########################################2nd Iteration  Deficit/Conflict iteration ###################################
        # print('\n\n########################################2nd Iteration  Deficit/Conflict iteration ###################################')
        for i, month in enumerate(keys):
            try:
                deficit = data[month]
                # defining a variable to differentiate between current and target month
                curr_month_num = i
                curr_month = keys[curr_month_num]
                if keys[i] == list(all_data.keys())[-1]:
                    # print(f"Reached end of Given production data - {keys[i]}....closing operation")
                    break
            
                # if last month of given of preoduction data is reached stop
                if curr_month == list(all_data.keys())[-1]:
                    # print(f"Reached end of Given production data - {curr_month}....closing operation")
                    break
                if deficit<0:
                    print("\n\n--- Month {}, conflict {} ---".format(keys[curr_month_num],deficit))
                    #######add condition to stop on dec
                    if ('Dec' in keys[curr_month_num]):
                        print('**No pull in /push out allowed on Jan for firs two iteration...closing operation***')
                        break  
                    while deficit < 0:
                        print("~~~~~~~~~~~~ Current values in adjust build slot ~~~~~~~~~~~~~~~~~~~~~\n",all_data)
                        if ('Dec' in keys[i]) :
                            print("***--------Target month reached next year Jan-------saving last changes and closing operation***")
                            break
                        # Iterate through car models in the defined order (GT -> Touring -> Pure)
                        try:
                            print("--- Current target month {} ---".format(keys[i + 1]))
                        except:
                            break
                        for car_model in pushout_desired_order:
                            # Get all rows for the current car model and sort by 'MODEL_YEAR'
                            model_rows = production[production["PRODUCT_TRIM"] == car_model].sort_values(by="MODEL_YEAR")
                            floor_doh = doh_floor_ceil_df1[doh_floor_ceil_df1["dd_Trim"] == car_model]["amt_Floor_DOS"].values[0]
                            ceil_doh = doh_floor_ceil_df1[doh_floor_ceil_df1["dd_Trim"] == car_model]["amt_Ceiling_DOS"].values[0]
                            for idx, row in model_rows.iterrows():
                                abs_deficit = abs(deficit)
                                try:
                                    pass  # Placeholder for logic
                                except:
                                    pass  # Placeholder for logic
                                # ...existing code...
                                if total_days_of_supply_ith<floor_doh or total_days_of_supply_ith>ceil_doh or total_days_of_supply<floor_doh or total_days_of_supply>ceil_doh:
                                    pass  # Placeholder for logic
                                if deficit >= 0:
                                    print("----------------loop broke as surplus is adjusted ---------------------")
                                    break
                            # ...existing code...
                            if deficit >= 0:
                                print("----------------loop broke after iterating all model years ---------------------")
                                break
                        if deficit < 0:
                            print("Moving to the next month")
                            i += 1
                            if 'Dec' in keys[i]:
                                break
                    print(f"\n-----------------------------Operation done for {curr_month}---------------------------------------------------------------\n\n")
            except:
                break
        
        ################################################# Now 3rd iteration ############################################
        # print('\n\n################################################# Now 3rd iteration ############################################\n')
        
        
        ###### Simplified Logic
        ## If curr year in not a final year
        ### we create a apended list of current year months and all next year months 
        ##### check if the next year is final
        ######### if yes perfrom normal surplus iteration with appended list -2 month
        ######### if no check if Next to next year exists with atleast 2 months
        ############ if yes take complete appended list with curr and next with no subtarction
        ############ if 1 month then subtract one month from appended if no month subtract 2 
        ############### now we perform surplus on this list
        ## If curr year is final year 
        ### we perfrom normal surplus on the data with -2 month logic
        
        
        
        
        #### if Current year is final year
        if is_final_year == 1:
            # print('\n Current year is Final year in the data. Thus, Executing A Final Self Balance in 3rd iteration ')
            new_traversal_data = actual_data_present_v0
            
            # dont iterate over the last 2 months of the data
            new_traversal_data = new_traversal_data[:-2]            
            data = {key: all_data[key] for key in new_traversal_data if key in all_data}
            keys = list(data.keys()) 
            # print(data)
        #### if Current year is NOT a final year
        else:
            # Create year +1 and year + 2 list for cobine data creation and checks
            year_num_ny = int(year_num) + 1
            # get month name of final month of last year
            yr_month_list_ny = generate_month_list(year_num_ny)
            actual_data_present_ny = find_common_elements_ordered(yr_month_list_ny, all_keys)
            year_num_ny_2 = int(year_num) + 2
            # get month name of final month of last year
            yr_month_list_ny_2 = generate_month_list(year_num_ny_2)
            actual_data_present_ny_2 = find_common_elements_ordered(yr_month_list_ny_2, all_keys)
            
            # check if next year if final
            if year_num_ny == int(years_present[-1]):
                # append current and next year monthlist and perfrom -2 months
                new_traversal_data = actual_data_present_v0 + actual_data_present_ny
                new_traversal_data = new_traversal_data[:-2]
                # print('\n Next year is Final year in the data. Thus, Executing 3rd iteration with considering current and next month ')
            else:
                # this means yr_month_list_ny_2 is confirm final year as we are provided with only 27 months
                # check does it have atleast 2 months 
                len_actual_data_present_ny_2 = len(actual_data_present_ny_2)
                if len_actual_data_present_ny_2 >1:
                    new_traversal_data = actual_data_present_v0 + actual_data_present_ny
                    # print('\n Next year is not Final year in the data with > 1 months data . Thus, Executing 3rd iteration with considering current and next month without reduction on month')                    
                else:
                    new_traversal_data = actual_data_present_v0 + actual_data_present_ny
                    remove_month_num = 2 - len_actual_data_present_ny_2
                    new_traversal_data = actual_data_present_v0 + actual_data_present_ny[:-remove_month_num]
                    # print('\n Next year is not Final year in the data with < 2 months data . Thus, Executing 3rd iteration with considering current and next month with calculated reduction on month')                    
                            
            
        # #Get next year first month for current month iteration restriction 
        if is_final_year == 0:
            year_num_ny = int(year_num) + 1
            # get month name 
            yr_month_list_ny = generate_month_list(year_num_ny)
            actual_data_present_ny = find_common_elements_ordered(yr_month_list_ny, all_keys)
            # if not actual_data_present_ny:
            #     print('No next year data present')
            #     break                    
            ny_year_month = actual_data_present_ny[0]
            traversal_last_month = new_traversal_data[-1]
        # give acces to plus 2 months from end but iteration alwasy end at dec     
        special_inv_month_key_ny = new_traversal_data + next_two_months(new_traversal_data)
        data = {key: all_data[key] for key in new_traversal_data if key in all_data}
        keys = list(data.keys()) 
        # print(f"\n------------------------------------Data now  {data}-------------------------")
        # print(f"\n------------------------------------Performing final sweep on Year {year_num}-------------------------")
        # print(f"\n------------------------------------sweep data -{keys} -------------------------")
        
        #print(f"\n------------------------------------special_inv_month_key_ny -{special_inv_month_key_ny} -------------------------")
        for i, month in enumerate(keys):
            surplus = data[month]
            # defining a variable to differentiate between current and target month
            curr_month_num = i
            curr_month = keys[curr_month_num]
            if keys[i] == list(all_data.keys())[-1]:
                # print(f"Reached end of Given production data - {keys[i]}....closing operation")
                break
            # Final sweep iteration should not iterate its current month over to new year months
            if is_final_year == 0:
                if (ny_year_month in keys[curr_month_num]) :
                    # print('**No pull in after last month in 3rd iteration***')
                    break                           
            if surplus>0:
                # print("\n\n--- Month {}, surplus {} ---".format(keys[curr_month_num],surplus))
                
                if is_final_year == 0:
                    pass  # Fix: ensure this block is not empty
                    #######Now current month should stop at year_pull_in_end_month
                    # print('ny_year_month---and keys[curr_month_num]',ny_year_month,keys[curr_month_num])
                while surplus > 0:
                    pass  # Placeholder for logic to resolve surplus
                    # Condition to stop on next year Jan as Target
                    # print("~~~~~~~~~~~~ Current values in adjust build slot ~~~~~~~~~~~~~~~~~~~~~\n",all_data)
                    # if ('Dec' in keys[i]):
                    #     print("***--------Target month reached next year Jan-------saving last changes and closing operation***")
                    #     break
                    # Iterate through car models in the defined order (GT -> Touring -> Pure)
                    try:
                        pass  # Placeholder for logic
                    except:
                        pass  # Placeholder for logic
                    for car_model in pullin_desired_order:
                        floor_doh = doh_floor_ceil_df1[doh_floor_ceil_df1["dd_Trim"] == car_model]["amt_Floor_DOS"].values[0]
                        ceil_doh = doh_floor_ceil_df1[doh_floor_ceil_df1["dd_Trim"] == car_model]["amt_Ceiling_DOS"].values[0]
                        # Iterate through the sorted rows from oldest to newest MODEL_YEAR
                        for idx, row in model_rows.iterrows():
                            next_month = keys[i + 1]
                            next_month_production = row[next_month]
                            sub_val = min(next_month_production, surplus)
                            #product_id = row["Product ID"]
                            model_year = row['MODEL_YEAR']
                            current_invt = inventory.loc[inventory.index[idx], special_inv_month_key_ny[curr_month_num + 1]]
                            try:
                                sales_forecast_floor_doh = sales.loc[sales.index[idx], special_inv_month_key[i + 2:]].values[:]
                                sales_forecast_floor_doh = sales_forecast_floor_doh.astype(int).tolist()
                                days_per_month_floor = []
                                for dayinmon in special_inv_month_key[i + 2:]:
                                    days_per_month_floor.append(days_in_month(dayinmon))
                                    
                                adjustable_invt_floor = current_invt - calculate_amt_of_invt(floor_doh, sales_forecast_floor_doh, days_per_month_floor)
                                
#                                 current_invt_ceil = inventory.loc[inventory.index[idx], special_inv_month_key[curr_month_num]]
#                                 sales_forecast_ceil_doh = sales.loc[sales.index[idx], special_inv_month_key[curr_month_num + 1:]].values[:]
#                                 sales_forecast_ceil_doh = sales_forecast_ceil_doh.astype(int).tolist()
#                                 days_per_month_ceil = []
#                                 for dayinmon in special_inv_month_key[curr_month_num + 1:]:
#                                     days_per_month_ceil.append(days_in_month(dayinmon))
                                    
#                                 adjustable_invt_ceil = calculate_amt_of_invt(ceil_doh, sales_forecast_ceil_doh, days_per_month_ceil) - current_invt_ceil
#                                 if adjustable_invt_ceil<0:
#                                     invt_acceptable = 0
#                                 else:
#                                     invt_acceptable = min(adjustable_invt_floor,adjustable_invt_ceil)
                            
                            except Exception as e:
                                    # print('exception as :', e)
                                    pass
                            # Determine the pull value and update
                            pull_value = min(sub_val, adjustable_invt_floor)
                            # print(f"Pull value: {pull_value} for car: {car_model}, MODEL_YEAR: {row['MODEL_YEAR']}, month: {month}")
                            # Update values and adjust surplus
                            start_index = month_list_invt.index(month)
                            end_index = month_list_invt.index(next_month)
                            prev_month = month_list_invt[start_index-1]
                            # Sublist inclusive of start and end
                            sublist = month_list_invt[start_index:end_index + 1]
                            update_value_pull(pull_value, car_model, month, next_month, model_year)
                            update_inventory(sublist,car_model,model_year,prev_month)
                            surplus -= pull_value
                            ####### adjust_build_slot  data list updates here
                            #change super data
                            all_data[curr_month] = all_data[curr_month] - pull_value
                            all_data[next_month] = all_data[next_month] + pull_value
                            # change loop_data
                            data[curr_month] = data[curr_month] - pull_value
                            data[next_month] = data[next_month] + pull_value
                            #DOS CHECK 1 for pulled out record
                            # Sample sales forecast data
                            end_of_month_inventory = inventory.loc[inventory.index[idx], keys[curr_month_num]]
                            try:
                                sales_values = sales.loc[sales.index[idx], special_inv_month_key_ny[curr_month_num+1:]].values[:]
                            except:
                                #print('Breaking at Sales Values in except in iteration 3')
                                pass                                        
                            sales_values = sales_values.astype(int).tolist()
                            days_per_month = []
                            for dayinmon in special_inv_month_key_ny[curr_month_num+1:]:
                                days_per_month.append(days_in_month(dayinmon))
                            # Calculate total days of supply
                            total_days_of_supply = calculate_days_of_supply(end_of_month_inventory, sales_values,days_per_month)
                            dos.loc[(dos['PRODUCT_TRIM']==car_model) & (dos["MODEL_YEAR"] == model_year),curr_month_num] = float(total_days_of_supply)
                            #DOS CHECK 2 for pulled in record
                            end_of_month_inventory_ith = inventory.loc[inventory.index[idx], keys[i+1]]
                            sales_values_ith = sales.loc[sales.index[idx], special_inv_month_key_ny[i+2:]].values[:]
                            sales_values_ith = sales_values_ith.astype(int).tolist()
                            days_per_month_target = []
                            for dayinmon in special_inv_month_key_ny[i+2:]:
                                days_per_month_target.append(days_in_month(dayinmon))
                            # Calculate total days of supply
                            total_days_of_supply_ith = calculate_days_of_supply(end_of_month_inventory_ith, sales_values_ith,days_per_month_target)
                            dos.loc[(dos['PRODUCT_TRIM']==car_model) & (dos["MODEL_YEAR"] == model_year),keys[i+1]] = float(total_days_of_supply_ith)
                            #print('ALL total_days_of_supply_ith',total_days_of_supply_ith,'ALL days_per_month: ',days_per_month )
                        # print("Total days of supply for pulled in :", round(total_days_of_supply_ith, 2))
                            if total_days_of_supply_ith<floor_doh or total_days_of_supply_ith>ceil_doh or total_days_of_supply<floor_doh or total_days_of_supply>ceil_doh:
                                pass  # Placeholder for logic
                            

                            #print(f"New surplus: {surplus}, Index: {idx}")
                            # If surplus is fully adjusted, break out of the loop
                            if surplus <= 0:
                                break
                        # Check if surplus is resolved after iterating through all MODEL_YEARs for the car model
                        if surplus <= 0:
                            break
                    # If reached the last index and still have surplus, move to the next month
                    if surplus > 0:
                        # print("Moving to next month")
                        i += 1
                        if keys[i] == list(all_data.keys())[-1]:
                            break
                else:
                    pass
            # print(f"\n-----------------------------Operation done for {curr_month}---------------------------------------------------------------\n\n")
    # inventory.to_csv("final_inventory.csv", index=False)
    # production.to_csv("final_production.csv",index  = False)
    # production.to_csv('final_production.csv', index = False)
    # req_prod.to_csv('final_req_production.csv', index = False)
    # capacity.to_csv('final_capacity.csv', index = False)
    # total_production.to_csv('final_total_production.csv', index = False)
    # sales.to_csv('final_sales.csv', index = False)
    # dos.to_csv('final_dos.csv', index = False)
    return production, inventory, dos


## DATA IMPORT:
# doh_floor_ceil_df1

## INPUT FILES:
req_prod = pd.read_csv('./req_prod.csv')
print(req_prod.shape)
req_prod.head(2)
capacity = pd.read_csv('./capacity.csv')
capacity.columns = [col.replace('.1', '') for col in capacity.columns]
print(capacity.shape)
capacity.head(2)
production = pd.read_csv('./production.csv')
print(production.shape)
production.head(2)
inventory = pd.read_csv('./inventory.csv')
print(inventory.shape)
inventory.head(2)
sales = pd.read_csv('./sales.csv')
print(sales.shape)
sales.head(2)
dos = pd.read_csv('./dos.csv')
print(dos.shape)
dos.head(2)
pullin_desired_order = ['PURE', 'DREAM', 'TOURING', 'GT', 'GT-P', 'SAPPHIRE'] 
pushout_desired_order = ['SAPPHIRE', 'GT-P', 'GT', 'TOURING', 'DREAM', 'PURE']
inventory.iloc[:, [0, 1, 2, 4]]
capacity = capacity.iloc[:, 9:36]
dd_Trim = ['SAPPHIRE', 'GT-P', 'GT', 'TOURING', 'DREAM', 'PURE']
amt_Floor_DOS = 60
amt_Ceiling_DOS = 100
doh_floor_ceil_df1 = pd.DataFrame({'dd_Trim': dd_Trim,
                                   'amt_Floor_DOS': [amt_Floor_DOS] * len(dd_Trim),
                                   'amt_Ceiling_DOS': [amt_Ceiling_DOS] * len(dd_Trim)})
print(doh_floor_ceil_df1.shape)

## Function Call:
#Balance - Button Clicked

production, inventory, dos = ConstrainedPlan(req_prod,capacity,production,inventory,sales,dos,pullin_desired_order, pushout_desired_order,doh_floor_ceil_df1)

production

inventory

dos



import requests
model = "llama3"
prompt = "Explain the concept of streaming pipelines in AWS Lambda."
response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": model,
        "prompt": prompt
    }
)
# Print the full JSON response to inspect
print(response.json())


import requests
def call_ollama_model(model_name: str, prompt: str):
    """
    Sends a prompt to a locally running Ollama model and returns the response.
    """
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model_name,
        "prompt": prompt
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()  # Raise error for bad HTTP status
        data = response.json()
        if "response" in data:
            return data["response"]
        elif "error" in data:
            return f"Error from Ollama: {data['error']}"
        else:
            return "Unexpected response format."
    except requests.exceptions.ConnectionError:
        return "Could not connect to Ollama. Is it running on localhost:11434?"
    except requests.exceptions.HTTPError as http_err:
        return f"HTTP error occurred: {http_err}"
    except Exception as e:
        return f"An error occurred: {e}"
# Example usage
if __name__ == "__main__":
    model = "llama3"  # Make sure this model is pulled via `ollama pull llama3`
    prompt = "Explain the concept of streaming pipelines in AWS Lambda."
    result = call_ollama_model(model, prompt)
    print(result)















##UI CODE##########################################################################################################################
import streamlit as st
import pandas as pd
from pathlib import Path
import numpy as np
import calendar
import math

# -----------------------------
# Load Input Data
# -----------------------------
BASE_DIR = Path(__file__).parent

req_prod = pd.read_csv(BASE_DIR / 'req_prod.csv')
capacity = pd.read_csv(BASE_DIR / 'capacity.csv')
capacity.columns = [col.replace('.1', '') for col in capacity.columns]
production = pd.read_csv(BASE_DIR / 'production.csv')
inventory = pd.read_csv(BASE_DIR / 'inventory.csv')
sales = pd.read_csv(BASE_DIR / 'sales.csv')
dos = pd.read_csv(BASE_DIR / 'dos.csv')

pullin_desired_order = ['PURE', 'DREAM', 'TOURING', 'GT', 'GT-P', 'SAPPHIRE']
pushout_desired_order = ['SAPPHIRE', 'GT-P', 'GT', 'TOURING', 'DREAM', 'PURE']

inventory = inventory.iloc[:, [0, 1, 2, 4]]
capacity = capacity.iloc[:, 9:36]

dd_Trim = ['SAPPHIRE', 'GT-P', 'GT', 'TOURING', 'DREAM', 'PURE']
amt_Floor_DOS = 60
amt_Ceiling_DOS = 100
doh_floor_ceil_df1 = pd.DataFrame({
    'dd_Trim': dd_Trim,
    'amt_Floor_DOS': [amt_Floor_DOS] * len(dd_Trim),
    'amt_Ceiling_DOS': [amt_Ceiling_DOS] * len(dd_Trim)
})

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="Production Planning Dashboard", layout="wide")
st.title("📊 Production Planning Dashboard")

# Move Run Balance Plan button to the top
run_balance_clicked = st.button("⚖️ Run Balance Plan", key="run_balance_top")
run_balance_result = None
if run_balance_clicked:
    with st.spinner("Running Constrained Plan..."):
        production_out, inventory_out, dos_out = ConstrainedPlan(
            req_prod, capacity, production, inventory, sales, dos,
            pullin_desired_order, pushout_desired_order, doh_floor_ceil_df1
        )
    st.success("✅ Constrained Plan executed successfully!")
    run_balance_result = (production_out, inventory_out, dos_out)

st.sidebar.header("⚙️ Data Frames Viewer")
dataset_choice = st.sidebar.selectbox(
    "Select a dataset to view:",
    ["req_prod", "capacity", "production", "inventory", "sales", "dos"]
)

# Add filter controls
def get_columns_for_choice(choice):
    if choice == "req_prod":
        return req_prod.columns.tolist()
    elif choice == "capacity":
        return capacity.columns.tolist()
    elif choice == "production":
        return production.columns.tolist()
    elif choice == "inventory":
        return inventory.columns.tolist()
    elif choice == "sales":
        return sales.columns.tolist()
    elif choice == "dos":
        return dos.columns.tolist()
    else:
        return []

filter_column = st.sidebar.selectbox(
    "Filter column:",
    options=get_columns_for_choice(dataset_choice)
)
filter_value = st.sidebar.text_input("Filter value (exact match):", "")

# Helper to filter and edit any DataFrame
from streamlit import column_config

def filter_and_edit(df, name):
    filtered_df = df
    if filter_value:
        if filter_column in df.columns:
            filtered_df = df[df[filter_column].astype(str) == filter_value]
    # All columns editable by default
    edited_df = st.data_editor(
        filtered_df,
        key=f"edit_{name}",
        num_rows="dynamic",
        column_config={col: column_config.Column() for col in filtered_df.columns}
    )
    return edited_df

# Show and edit the selected dataset
if dataset_choice == "req_prod":
    req_prod = filter_and_edit(req_prod, "req_prod")
elif dataset_choice == "capacity":
    capacity = filter_and_edit(capacity, "capacity")
elif dataset_choice == "production":
    production = filter_and_edit(production, "production")
elif dataset_choice == "inventory":
    inventory = filter_and_edit(inventory, "inventory")
elif dataset_choice == "sales":
    sales = filter_and_edit(sales, "sales")
elif dataset_choice == "dos":
    dos = filter_and_edit(dos, "dos")

# After the table, show the results if the button was clicked
if run_balance_result is not None:
    production_out, inventory_out, dos_out = run_balance_result
    st.subheader("📦 Updated Production")
    st.data_editor(production_out, key="edit_production_out", num_rows="dynamic")

    st.subheader("🏭 Updated Inventory")
    st.data_editor(inventory_out, key="edit_inventory_out", num_rows="dynamic")

    st.subheader("📈 Updated DOS")
    st.data_editor(dos_out, key="edit_dos_out", num_rows="dynamic")
